# frozen_string_literal: true

# Browser primitives for interacting with the Wikifunctions UI.
# Handles browser lifecycle, login, DOM helpers, and low-level UI
# interactions (lookups, mode selectors, literals, publish dialog).

require 'fileutils'
require 'selenium-webdriver'
require 'json'
require 'net/http'
require 'uri'

AI_DISCLOSURE = 'Created with AI assistance (Claude Opus 4.6)'

class WfBrowser
  WF_BASE = 'https://www.wikifunctions.org'
  WF_API = "#{WF_BASE}/w/api.php"
  PROFILE_DIR = File.expand_path('../../.browser-profile', __FILE__)

  attr_reader :driver, :function_zid, :api_info

  def initialize(browser: :firefox, delay: 0.7)
    @browser = browser
    @delay = delay
    @driver = nil
    @wait = nil
    @function_zid = nil
    @api_info = {}
    @prefix = nil
  end

  # ── Browser lifecycle ────────────────────────────────────────

  def launch
    log "Launching #{@browser} (profile: #{PROFILE_DIR})..."

    # Clear stale lock files from previous sessions
    %w[SingletonLock SingletonSocket SingletonCookie].each do |f|
      path = File.join(PROFILE_DIR, f)
      File.delete(path) if File.exist?(path)
    end

    case @browser
    when :chrome
      options = Selenium::WebDriver::Chrome::Options.new
      options.add_argument("--user-data-dir=#{PROFILE_DIR}")
      @driver = Selenium::WebDriver.for(:chrome, options: options)
    when :firefox
      options = Selenium::WebDriver::Firefox::Options.new
      options.add_argument('-profile')
      options.add_argument(PROFILE_DIR)
      FileUtils.mkdir_p(PROFILE_DIR) unless Dir.exist?(PROFILE_DIR)
      @driver = Selenium::WebDriver.for(:firefox, options: options)
    else
      @driver = Selenium::WebDriver.for(@browser)
    end
    @driver.manage.window.resize_to(1400, 900)
    @wait = Selenium::WebDriver::Wait.new(timeout: 30)
    @driver.navigate.to(WF_BASE)
    self
  end

  def quit
    @driver&.quit
  rescue StandardError
    # Best effort — don't fail if the browser is already gone
  end

  def ensure_logged_in
    log 'Checking login status...'
    wait_for_mw_config

    if (username = check_username)
      log "Logged in as #{username}."
      return username
    end

    log 'Not logged in. Please log in in the browser window.'
    poll_until(timeout: 600, interval: 5, waiting_for: 'login') do
      check_username
    end.tap { |u| log "Logged in as #{u}." }
  end

  # ── Navigation ───────────────────────────────────────────────

  def navigate_to(url)
    @driver.navigate.to(url)
  end

  def current_url
    @driver.current_url
  end

  def set_function_zid(zid)
    @function_zid = zid
  end

  # ── API metadata ─────────────────────────────────────────────

  def fetch_metadata_for(zids)
    zids = zids.compact.uniq
    return if zids.empty?

    log "Fetching metadata for #{zids.join(', ')}..."

    uri = URI(WF_API)
    uri.query = URI.encode_www_form(
      action: 'wikilambda_fetch', zids: zids.join('|'), format: 'json'
    )
    data = JSON.parse(Net::HTTP.get(uri))

    zids.each do |zid|
      raw = data.dig(zid, 'wikilambda_fetch')
      next unless raw

      zobj = raw.is_a?(String) ? JSON.parse(raw) : raw
      inner = zobj['Z2K2'] || zobj
      name = en_label(zobj['Z2K3'])
      args = (inner['Z8K1'] || []).filter_map { |a|
        next unless a.is_a?(Hash) && a['Z17K2']

        [a['Z17K2'], en_label(a['Z17K3'])]
      }.to_h
      output_type = inner['Z8K2']
      @api_info[zid] = { name: name, args: args, output_type: output_type }
      arg_list = args.values.join(', ')
      log "  #{zid}: #{name}#{arg_list.empty? ? '' : " (#{arg_list})"}"
    end
  end

  def validate_function(expect_args)
    return unless expect_args

    info = @api_info[@function_zid]
    unless info
      log "  WARNING: no metadata for #{@function_zid}, skipping validation."
      return
    end

    actual_labels = info[:args].values.map(&:downcase)
    expected_labels = expect_args.map(&:downcase)

    if actual_labels == expected_labels
      log "  Validated: arguments match (#{expect_args.join(', ')})."
    else
      log "  WARNING: argument mismatch!"
      log "    Expected: #{expect_args.join(', ')}"
      log "    Actual:   #{info[:args].values.join(', ')}"
      log "  Continuing anyway — review carefully before publishing."
    end
  end

  # ── Publish dialog and verification ──────────────────────────

  def open_publish_dialog(summary)
    step 'Opening publish dialog'
    publish_btn = @wait.until { safe_find('[data-testid="publish-button"]') }
    scroll_to(publish_btn)
    short_pause
    publish_btn.click
    pause

    @wait.until { safe_find('[data-testid="publish-dialog"]') }
    short_pause

    full_summary = summary.to_s.empty? ? AI_DISCLOSURE : "#{summary} -- #{AI_DISCLOSURE}"
    step "Edit summary: #{full_summary}"
    summary_input = @driver.find_element(
      css: '.ext-wikilambda-app-publish-dialog__summary-input input, ' \
           '[data-testid="publish-dialog"] input.cdx-text-input__input'
    )
    summary_input.clear
    summary_input.send_keys(full_summary)
    pause
  end

  def verify_published
    log ''
    log 'Click Publish to finalize. The script will verify afterwards.'

    pre_url = @driver.current_url
    new_zid = poll_until(timeout: 300, interval: 3, waiting_for: 'publish') do
      url = @driver.current_url
      next nil if url == pre_url

      url.match(%r{/(Z\d+)(?:\?|$)})&.[](1)
    end

    log "Published: #{new_zid}"
    log 'Verifying via API...'

    uri = URI(WF_API)
    uri.query = URI.encode_www_form(
      action: 'wikilambda_fetch', zids: new_zid, format: 'json'
    )
    data = JSON.parse(Net::HTTP.get(uri))
    raw = data.dig(new_zid, 'wikilambda_fetch')

    if raw
      zobj = raw.is_a?(String) ? JSON.parse(raw) : raw
      inner = zobj['Z2K2'] || zobj
      obj_type = inner['Z1K1']
      label = en_label(zobj.dig('Z2K3'))
      log "  #{new_zid}: #{label} (type: #{obj_type})"
      log '  Verified.'
    else
      log "  WARNING: could not fetch #{new_zid} — it may take a moment to propagate."
    end

    new_zid
  end

  # ── UI primitives: labels ────────────────────────────────────

  def set_label(label)
    return unless label

    step "Setting label: #{label}"
    selectors = [
      '[data-testid="text-input"]',
      '[id*="Z2K3"] input.cdx-text-input__input',
      '.ext-wikilambda-app-about-edit-metadata__label input',
      'input.ext-wikilambda-app-about-edit-metadata-dialog__label-input',
    ]
    selectors.each do |sel|
      begin
        input = @driver.find_element(css: sel)
        next unless input.displayed?

        scroll_to(input)
        short_pause
        input.clear
        input.send_keys(label)
        return
      rescue Selenium::WebDriver::Error::NoSuchElementError
        next
      end
    end

    log "  WARNING: could not find label input — set it manually."
  end

  # ── UI primitives: lookups ───────────────────────────────────

  def select_in_lookup(element_id, zid)
    container = @driver.find_element(id: element_id)
    begin
      input = container.find_element(css: 'input.cdx-text-input__input')
    rescue Selenium::WebDriver::Error::NoSuchElementError
      # No lookup input — a function may already be pre-selected.
      log "  (no lookup input found — function may be pre-selected, skipping)"
      return
    end
    scroll_to(input)
    short_pause
    input.clear
    input.send_keys(zid)
    sleep 2
    input.send_keys(:arrow_down)
    short_pause
    input.send_keys(:return)
    short_pause
  end

  # ── UI primitives: mode selector ─────────────────────────────

  def switch_mode(keypath, mode_value)
    el = @driver.find_element(id: keypath)

    # Check if already in the desired mode (e.g., function call pre-selected)
    if mode_value == 'Z7'
      existing_fc = el.find_elements(css: '[data-testid="z-function-call"]')
      if existing_fc.any?
        log "  (already in function call mode, skipping switch)"
        return
      end
    end

    btn = el.find_element(css: '[data-testid="mode-selector-button"]')
    scroll_to(btn)
    short_pause
    btn.click
    short_pause

    mode_labels = {
      'Z7' => 'Function call',
      'Z9' => 'Reference',
      'Z18' => 'Argument reference'
    }
    label = mode_labels[mode_value] || mode_value

    @wait.until do
      @driver.execute_script(<<~JS, label)
        const items = document.querySelectorAll('.cdx-menu-item');
        for (const item of items) {
          if (item.offsetParent !== null && item.textContent.trim().includes(arguments[0])) {
            item.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
            item.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
            item.dispatchEvent(new MouseEvent('click', { bubbles: true }));
            return true;
          }
        }
        return false;
      JS
    end
  end

  # ── UI primitives: expand/collapse ───────────────────────────

  def expand_at(keypath)
    z7k1_id = "#{keypath}-Z7K1"
    return if safe_find("[id='#{z7k1_id}']")

    el = @driver.find_element(id: keypath)
    click_first(el,
                '[data-testid="object-to-string-link"]',
                '[data-testid="expanded-toggle"]')
  end

  # ── UI primitives: argument references ───────────────────────

  def select_arg_ref(keypath, ref_name)
    impl_args = @api_info.dig(@function_zid, :args) || {}
    arg_key = impl_args.find { |_k, v| v.downcase == ref_name.downcase }&.first

    unless arg_key
      log "    WARNING: no argument '#{ref_name}' found in #{@function_zid}"
      return
    end

    el = @driver.find_element(id: keypath)

    begin
      native_select = el.find_element(css: 'select')
      scroll_to(native_select)
      short_pause
      Selenium::WebDriver::Support::Select.new(native_select).select_by(:text, ref_name)
      return
    rescue Selenium::WebDriver::Error::NoSuchElementError
      # Not a native select
    end

    handle = el.find_element(css: '.cdx-select__handle, [role="combobox"]')
    scroll_to(handle)
    short_pause
    handle.click
    short_pause

    arg_keys = impl_args.keys
    position = arg_keys.index(arg_key) || 0
    (position + 1).times { handle.send_keys(:arrow_down); sleep 0.2 }
    handle.send_keys(:return)
  end

  # ── UI primitives: literal values ────────────────────────────

  def fill_literal(keypath, value, type)
    el = @driver.find_element(id: keypath)

    case type
    when 'Z6092', 'Z6091' # Wikidata property or item reference
      input = el.find_element(css: [
        '[data-testid="wikidata-entity-selector"] input.cdx-text-input__input',
        'input.cdx-text-input__input'
      ].join(', '))
      scroll_to(input)
      short_pause
      input.clear
      input.send_keys(value)
      pause
      input.send_keys(:arrow_down)
      short_pause
      input.send_keys(:return)

    when 'Z6', 'Z16683', 'Z13518' # String, Integer, Natural Number
      input = el.find_element(css: '[data-testid="text-input"], input.cdx-text-input__input, input[type="number"], input')
      input.clear
      input.send_keys(value)

    else
      log "    WARNING: unknown literal type #{type} -- trying text input"
      begin
        input = el.find_element(css: 'input')
        input.clear
        input.send_keys(value)
      rescue Selenium::WebDriver::Error::NoSuchElementError
        log '    Could not find an input. Set this value manually.'
      end
    end
  end

  # ── UI primitives: "Edit source" ─────────────────────────────

  def click_edit_source
    step 'Clicking "Edit source"...'
    @driver.execute_script(<<~JS)
      const links = document.querySelectorAll('a, button, span[role="tab"]');
      for (const link of links) {
        if (link.textContent.trim() === 'Edit source' || link.textContent.trim() === 'edit') {
          link.click();
          return;
        }
      }
    JS
  end

  # ── Logging ──────────────────────────────────────────────────

  def log(msg)
    puts msg
    $stdout.flush
  end

  def step(msg)
    log "-> #{msg}"
  end

  def pause
    sleep @delay
  end

  def short_pause
    sleep [@delay * 0.4, 0.5].max
  end

  # ── Helpers ──────────────────────────────────────────────────

  def poll_until(timeout:, interval:, waiting_for: 'condition')
    deadline = Time.now + timeout
    loop do
      raise "Timed out waiting for #{waiting_for} (#{timeout / 60}min)." if Time.now > deadline

      result = yield
      return result if result

      sleep interval
    end
  end

  def safe_find(css)
    @driver.find_element(css: css)
  rescue Selenium::WebDriver::Error::NoSuchElementError
    nil
  end

  def scroll_to(element)
    @driver.execute_script('arguments[0].scrollIntoView({block: "center"})', element)
  end

  def click_first(context, *selectors)
    selectors.each do |sel|
      begin
        context.find_element(css: sel).click
        return sel
      rescue Selenium::WebDriver::Error::NoSuchElementError
        next
      end
    end
    nil
  end

  def en_label(z12)
    return '' unless z12.is_a?(Hash)

    (z12['Z12K1'] || []).each do |item|
      next unless item.is_a?(Hash)
      return item['Z11K2'] if item['Z11K1'] == 'Z1002'
    end
    ''
  end

  def wait_for_mw_config
    @wait.until do
      @driver.execute_script(
        'return typeof mw !== "undefined" && typeof mw.config !== "undefined"'
      )
    end
  rescue Selenium::WebDriver::Error::TimeoutError
    nil
  end

  def check_username
    @driver.execute_script(
      'return (typeof mw !== "undefined" && mw.config) ' \
      '? mw.config.get("wgUserName") : null'
    )
  rescue StandardError
    nil
  end
end
