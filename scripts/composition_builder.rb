#!/usr/bin/env ruby
# frozen_string_literal: true

# Browser automation toolkit for Wikifunctions composition building.
#
# Launches a browser, navigates to the function, validates it,
# clicks "Add implementation", fills in the composition tree,
# and stops with the publish dialog open for you to confirm.
#
# Usage:
#   ruby scripts/composition_builder.rb zobjects/my_composition.json
#   ruby scripts/composition_builder.rb zobjects/my_composition.json --delay 2 --browser chrome
#
# Input JSON format:
#   {
#     "function_zid": "Z33588",
#     "label": "composition using Z811, Z28513, Z29691, Z14046",
#     "summary": "Add composition: first statement with qualifier",
#     "expect_args": ["item", "property", "qualifier"],
#     "composition": {
#       "call": "Z811", "name": "first element",
#       "args": {
#         "Z811K1": {
#           "label": "list",
#           "call": "Z28513", "name": "filter statements by qualifiers",
#           "args": { ... }
#         }
#       }
#     }
#   }
#
# - function_zid: if present, the script navigates directly to the function
#   and clicks "Add implementation". If absent, waits for you to navigate.
# - implementation_zid: if present, edit this existing implementation instead
#   of creating a new one. The script opens it, clears the composition, and
#   fills in the new tree.
# - label: name for the implementation (shown in the Wikifunctions UI).
# - expect_args: optional list of expected argument labels for validation.
# - composition: the tree to fill in. "name" and "label" are optional
#   human-readable annotations.

require 'fileutils'
require 'selenium-webdriver'
require 'json'
require 'net/http'
require 'uri'
require 'optparse'

AI_DISCLOSURE = 'Created with AI assistance (Claude Opus 4.6)'

class WikifunctionsBrowser
  WF_BASE = 'https://www.wikifunctions.org'
  WF_API = "#{WF_BASE}/w/api.php"
  PROFILE_DIR = File.expand_path('../../.browser-profile', __FILE__)

  attr_reader :driver, :function_zid

  def initialize(browser: :firefox, delay: 0.7)
    @browser = browser
    @delay = delay
    @driver = nil
    @wait = nil
    @function_zid = nil
    @api_info = {}
    @prefix = nil
  end

  # ── Public routines ──────────────────────────────────────────

  # Launch the browser and open Wikifunctions.
  # Uses a persistent profile directory so login sessions survive restarts.
  def launch
    log "Launching #{@browser} (profile: #{PROFILE_DIR})..."
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

  # Wait until the user is logged in. Returns the username.
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

  # Fetch metadata from the API for a list of ZIDs plus the function being
  # implemented. Returns @api_info hash.
  def fetch_metadata(composition)
    zids = (collect_call_zids(composition) + [@function_zid]).compact.uniq
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

  # Validate that the function's arguments match what we expect.
  # expect_args is an array of label strings, e.g. ["item", "property", "qualifier"].
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

  # Navigate to the function page, validate, and click "Add implementation".
  # Sets @function_zid.
  def navigate_to_function(zid)
    @function_zid = zid
    url = "#{WF_BASE}/view/en/#{zid}"
    step "Opening function page: #{url}"
    @driver.navigate.to(url)

    log '  Waiting for page to load...'
    @wait.until { safe_find('[data-testid="function-implementations-table"]') }
    log "  Function page loaded: #{zid}"
    pause
  end

  # Click the "Add implementation" link on a function page.
  # Waits for the implementation editor to appear.
  def click_add_implementation
    step 'Clicking "Add implementation"...'

    # The add link is inside the implementations table
    add_link = @driver.find_element(
      css: '[data-testid="function-implementations-table"] [data-testid="add-link"]'
    )
    scroll_to(add_link)
    short_pause
    add_link.click

    log '  Waiting for implementation editor...'
    @wait.until { safe_find('[data-testid="implementation-radio"]') }
    log '  Implementation editor ready.'
    pause
  end

  # Navigate to an existing implementation and enter edit mode.
  def navigate_to_edit(impl_zid)
    url = "#{WF_BASE}/view/en/#{impl_zid}"
    step "Opening implementation page: #{url}"
    @driver.navigate.to(url)

    log '  Waiting for page to load...'
    @wait.until { safe_find('.ext-wikilambda-app') }
    pause

    # Click "Edit source" — find the link by its text content
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

    log '  Waiting for implementation editor...'
    @wait.until { safe_find('[data-testid="implementation-radio"]') }
    log '  Edit mode ready.'
    pause
  end

  # Read the function ZID from an implementation being edited.
  # Looks at the Z14K1 field or the page metadata.
  def detect_function_zid_from_edit
    # Try mw.config for the page's function reference
    @function_zid = @driver.execute_script(<<~JS)
      // Try to find the function ZID from the implementation-function field
      const el = document.querySelector('[data-testid="implementation-function"] .ext-wikilambda-app-function-call');
      if (el) {
        const text = el.textContent;
        const match = text.match(/(Z\\d+)/);
        if (match) return match[1];
      }
      // Fallback: check URL for Z14K1
      const url = window.location.href;
      const m = url.match(/Z14K1=(Z\\d+)/);
      return m ? m[1] : null;
    JS

    log "  Function: #{@function_zid}" if @function_zid
    @function_zid
  end

  # Clear the existing composition by toggling Code → Composition.
  def clear_composition
    step 'Clearing existing composition (toggle Code → Composition)...'

    # Switch to Code
    code_radio = @driver.find_element(
      css: '[data-testid="implementation-radio"] input[value="Z14K3"]'
    )
    @driver.execute_script('arguments[0].click()', code_radio)
    pause

    # Switch back to Composition
    comp_radio = @driver.find_element(
      css: '[data-testid="implementation-radio"] input[value="Z14K2"]'
    )
    @driver.execute_script('arguments[0].click()', comp_radio)
    pause
    log '  Composition cleared.'
  end

  # Wait until the user manually reaches the composition editor.
  # Detects the page type and reads the function ZID from the URL.
  def wait_for_composition_ui
    log ''
    log 'Navigate to the composition editor when ready.'
    log '  - Open a function, click "Add implementation", or'
    log '  - Go to Special:CreateObject with zid=Z14'
    log 'The script will detect the page and continue.'

    @function_zid = poll_until(timeout: 600, interval: 3, waiting_for: 'composition UI') do
      detect_function_zid
    end

    log "Function: #{@function_zid}"
    @function_zid
  end

  # Set the implementation label (name) in the UI.
  def set_label(label)
    return unless label

    step "Setting label: #{label}"
    # The label input location varies — try several selectors.
    selectors = [
      '[data-testid="text-input"]',                                        # generic text input
      '[id*="Z2K3"] input.cdx-text-input__input',                         # label key input
      '.ext-wikilambda-app-about-edit-metadata__label input',              # about section
      'input.ext-wikilambda-app-about-edit-metadata-dialog__label-input',  # dialog variant
    ]
    selectors.each do |sel|
      begin
        input = @driver.find_element(css: sel)
        # Verify it's visible and near the top of the page (not a nested input)
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

  # Ensure Composition is selected, expand the root, and fill the tree.
  def build_composition(composition)
    ensure_composition_selected
    expand_root
    build_function_call(composition, @prefix)
  end

  # Click Publish, fill in the edit summary, and stop.
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

  # Wait for the user to publish, then verify via API.
  # Polls the current URL for a redirect to the new object page.
  def verify_published
    log ''
    log 'Click Publish to finalize. The script will verify afterwards.'

    pre_url = @driver.current_url
    new_zid = poll_until(timeout: 300, interval: 3, waiting_for: 'publish') do
      url = @driver.current_url
      next nil if url == pre_url

      # After publishing, the URL typically contains the new ZID
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

  private

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

  # ── Polling ──────────────────────────────────────────────────

  def poll_until(timeout:, interval:, waiting_for: 'condition')
    deadline = Time.now + timeout
    loop do
      if Time.now > deadline
        raise "Timed out waiting for #{waiting_for} (#{timeout / 60}min)."
      end

      result = yield
      return result if result

      sleep interval
    end
  end

  # ── Login detection ──────────────────────────────────────────

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

  # ── Page detection ───────────────────────────────────────────

  def detect_function_zid
    url = @driver.current_url

    # New implementation: Special:CreateObject?zid=Z14&Z14K1=Z33600
    if url.include?('CreateObject') && url =~ /Z14K1=(Z\d+)/
      zid = ::Regexp.last_match(1)
      return zid if safe_find('[data-testid="implementation-radio"]')
    end

    nil
  end

  # ── Composition type selection ───────────────────────────────

  def ensure_composition_selected
    radio = @driver.find_element(
      css: '[data-testid="implementation-radio"] input[value="Z14K2"]'
    )
    unless radio.selected?
      step 'Selecting Composition type'
      @driver.execute_script('arguments[0].click()', radio)
      pause
    end
  end

  # ── Root expansion and keypath discovery ─────────────────────

  def expand_root
    step 'Expanding composition root'
    content = @driver.find_element(css: '[data-testid="implementation-content"]')

    # Try expanding — may need multiple attempts if the first click
    # hits a toggle that was already in the wrong state.
    2.times do
      # Check if Z7K1 is already visible
      z7k1 = @driver.find_elements(css: '[id*="Z14K2"][id*="Z7K1"]')
                     .find { |el| el.attribute('class')&.include?('object-key-value') }
      break if z7k1

      click_first(content,
                  '[data-testid="object-to-string-link"]',
                  '[data-testid="expanded-toggle"]')
      pause
    end

    # Element IDs encode the keypath with dashes, e.g. "main-Z2K2-Z14K2-Z7K1".
    # Find the Z7K1 element and strip the suffix to get the prefix.
    z7k1 = @wait.until do
      @driver.find_elements(css: '[id*="Z14K2"][id*="Z7K1"]')
             .find { |el| el.attribute('class')&.include?('object-key-value') }
    end
    @prefix = z7k1.attribute('id').sub(/-Z7K1$/, '')
    log "  Keypath prefix: #{@prefix}"
  end

  # ── Recursive composition builder ────────────────────────────

  def build_function_call(node, keypath)
    zid = node['call']
    step "Select function: #{zid} (#{func_name(zid, node)})"
    select_in_lookup("#{keypath}-Z7K1", zid, node)
    pause

    args = node['args'] || {}
    return if args.empty?

    first_id = "#{keypath}-#{args.keys.first}"
    log "  Waiting for argument fields..."
    @wait.until { safe_find("[id='#{first_id}']") }
    short_pause

    args.each do |arg_key, arg_node|
      fill_argument(zid, keypath, arg_key, arg_node)
    end
  end

  def fill_argument(parent_zid, parent_keypath, arg_key, node)
    label = arg_label_for(parent_zid, arg_key, node)
    keypath = "#{parent_keypath}-#{arg_key}"

    if node['call']
      step "  #{label} -> function call: #{node['call']} (#{func_name(node['call'], node)})"
      switch_mode(keypath, 'Z7')
      pause
      expand_at(keypath)
      pause
      build_function_call(node, keypath)

    elsif node['ref']
      step "  #{label} -> argument reference: #{node['ref']}"
      switch_mode(keypath, 'Z18')
      pause
      select_arg_ref(keypath, node['ref'])
      pause

    elsif node['literal']
      step "  #{label} -> literal #{node['type']}: #{node['literal']}"
      fill_literal(keypath, node['literal'], node['type'])
      pause
    end
  end

  # ── UI interaction primitives ────────────────────────────────

  def switch_mode(keypath, mode_value)
    el = @driver.find_element(id: keypath)
    btn = el.find_element(css: '[data-testid="mode-selector-button"]')
    scroll_to(btn)
    short_pause
    btn.click
    short_pause

    # Codex menus don't expose data-value as DOM attributes, so we
    # find items by their visible text content.
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

  def expand_at(keypath)
    # If Z7K1 is already visible inside this element, it's already expanded.
    z7k1_id = "#{keypath}-Z7K1"
    return if safe_find("[id='#{z7k1_id}']")

    el = @driver.find_element(id: keypath)
    click_first(el,
                '[data-testid="object-to-string-link"]',
                '[data-testid="expanded-toggle"]')
  end

  def select_in_lookup(element_id, zid, _node = nil)
    container = @driver.find_element(id: element_id)
    input = container.find_element(css: 'input.cdx-text-input__input')
    scroll_to(input)
    short_pause
    input.clear
    # Type the ZID — name-based search is unreliable in the Wikifunctions lookup.
    input.send_keys(zid)
    # Wait for API search results to populate the dropdown, then use
    # keyboard to select the first result. This avoids all DOM-clicking
    # issues with Codex menus (which don't expose data-value attributes).
    # Use a longer wait here — the API search can be slow.
    sleep 2
    input.send_keys(:arrow_down)
    short_pause
    input.send_keys(:return)
  end

  def select_arg_ref(keypath, ref_name)
    impl_args = @api_info.dig(@function_zid, :args) || {}
    arg_key = impl_args.find { |_k, v| v.downcase == ref_name.downcase }&.first

    unless arg_key
      log "    WARNING: no argument '#{ref_name}' found in #{@function_zid}"
      return
    end

    el = @driver.find_element(id: keypath)

    # CdxSelect may render as a native <select> or a custom Vue component.
    # Try native <select> first, then fall back to the Codex custom select.
    begin
      native_select = el.find_element(css: 'select')
      scroll_to(native_select)
      short_pause
      Selenium::WebDriver::Support::Select.new(native_select).select_by(:text, ref_name)
      return
    rescue Selenium::WebDriver::Error::NoSuchElementError
      # Not a native select — try the Codex custom select
    end

    # Codex custom select: click handle, then pick by keyboard
    handle = el.find_element(css: '.cdx-select__handle, [role="combobox"]')
    scroll_to(handle)
    short_pause
    handle.click
    short_pause

    # Find the argument's position in the function signature so we know
    # how many times to press ArrowDown.
    arg_keys = impl_args.keys
    position = arg_keys.index(arg_key) || 0
    (position + 1).times { handle.send_keys(:arrow_down); sleep 0.2 }
    handle.send_keys(:return)
  end

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

  # ── Metadata helpers ─────────────────────────────────────────

  def collect_call_zids(node)
    return [] unless node.is_a?(Hash) && node['call']

    [node['call']] + (node['args'] || {}).values.flat_map { |v| collect_call_zids(v) }
  end

  def en_label(z12)
    return '' unless z12.is_a?(Hash)

    (z12['Z12K1'] || []).each do |item|
      next unless item.is_a?(Hash)
      return item['Z11K2'] if item['Z11K1'] == 'Z1002'
    end
    ''
  end

  def func_name(zid, node = nil)
    node&.dig('name') || @api_info.dig(zid, :name) || zid
  end

  def arg_label_for(parent_zid, arg_key, arg_node)
    arg_node&.dig('label') || @api_info.dig(parent_zid, :args, arg_key) || arg_key
  end

  # ── DOM helpers ──────────────────────────────────────────────

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
end

# ── CLI ────────────────────────────────────────────────────────

if __FILE__ == $PROGRAM_NAME
  options = { delay: 0.7, browser: :firefox }

  OptionParser.new do |opts|
    opts.banner = "Usage: #{$PROGRAM_NAME} [COMPOSITION_FILE] [options]"
    opts.separator ''
    opts.separator 'Launches a browser, navigates to the function, validates it,'
    opts.separator 'adds a composition implementation, and opens the publish dialog.'
    opts.separator ''
    opts.on('--delay N', Float, "Seconds between steps (default: #{options[:delay]})") do |d|
      options[:delay] = d
    end
    opts.on('--browser NAME', "firefox or chrome (default: #{options[:browser]})") do |b|
      options[:browser] = b.to_sym
    end
  end.parse!

  composition_file = ARGV.shift
  spec = if composition_file
           JSON.parse(File.read(composition_file))
         else
           warn 'No composition file given. Will launch browser and wait for login only.'
           nil
         end

  wf = WikifunctionsBrowser.new(browser: options[:browser], delay: options[:delay])

  begin
    wf.launch
    wf.ensure_logged_in

    if spec
      if spec['implementation_zid']
        # Edit an existing implementation
        wf.navigate_to_edit(spec['implementation_zid'])
        # Use function_zid from the spec; fall back to detecting from the page
        if spec['function_zid']
          wf.instance_variable_set(:@function_zid, spec['function_zid'])
        else
          wf.detect_function_zid_from_edit
        end
        wf.fetch_metadata(spec['composition'])
        wf.clear_composition
      elsif spec['function_zid']
        # Create a new implementation
        wf.navigate_to_function(spec['function_zid'])
        wf.fetch_metadata(spec['composition'])
        wf.validate_function(spec['expect_args'])
        wf.click_add_implementation
      else
        # Wait for user to navigate manually
        wf.wait_for_composition_ui
        wf.fetch_metadata(spec['composition'])
        wf.validate_function(spec['expect_args'])
      end

      wf.set_label(spec['label'])
      wf.build_composition(spec['composition'])
      wf.open_publish_dialog(spec['summary'])
      new_zid = wf.verify_published
      puts ''
      puts "Done: #{new_zid}"
    else
      wf.wait_for_composition_ui
      puts ''
      puts "Detected function: #{wf.function_zid}"
      puts 'No composition file provided. Browser left open.'
    end
  rescue StandardError => e
    puts "\nERROR: #{e.message}"
    e.backtrace.first(5).each { |line| puts "  #{line}" }
    puts 'Browser left open for inspection.'
  end

  puts '(Browser stays open. Press Ctrl+C to quit.)'
  begin
    sleep
  rescue Interrupt
    puts "\nDone."
  end
end
