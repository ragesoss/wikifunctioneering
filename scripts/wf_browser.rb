# frozen_string_literal: true

# Browser primitives for interacting with the Wikifunctions UI.
# Handles browser lifecycle, login, DOM helpers, and low-level UI
# interactions (lookups, mode selectors, literals, publish dialog).

require 'fileutils'
require 'selenium-webdriver'
require 'json'
require 'net/http'
require 'uri'

require_relative 'wf_api'

AI_DISCLOSURE = 'Created with AI assistance (Claude Opus 4.6)'

class WfBrowser
  include WfApi

  WF_BASE = 'https://www.wikifunctions.org'
  WF_API = "#{WF_BASE}/w/api.php"
  PROFILE_DIR = File.expand_path('../../.browser-profile', __FILE__)

  attr_reader :driver, :function_zid, :api_info

  def initialize(browser: :firefox, delay: 0.25)
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

    # Refuse to proceed if another browser is live on this profile — launching
    # a second instance with the same user-data-dir corrupts cookies and logs
    # the first instance out.
    ensure_profile_free!

    # Clean up lock files left behind by a crashed/killed previous session.
    # (ensure_profile_free! has already confirmed these don't belong to a live
    # process.)
    %w[SingletonLock SingletonSocket SingletonCookie lock .parentlock].each do |f|
      path = File.join(PROFILE_DIR, f)
      File.delete(path) if File.symlink?(path) || File.exist?(path)
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

  # Append the AI disclosure to a user-provided edit summary (or use the
  # disclosure alone if the user summary is empty). Used by both the UI
  # publish dialog and the API-mode edit path so both leave the same
  # trail in page history.
  def ai_summary(summary)
    summary.to_s.empty? ? AI_DISCLOSURE : "#{summary} -- #{AI_DISCLOSURE}"
  end

  # ── Publish dialog and verification ──────────────────────────

  def open_publish_dialog(summary)
    step 'Opening publish dialog'
    publish_btn = slow_wait(tag: 'publish-button') { safe_find('[data-testid="publish-button"]') }
    scroll_to(publish_btn)
    short_pause
    publish_btn.click
    pause

    slow_wait(tag: 'publish-dialog') { safe_find('[data-testid="publish-dialog"]') }
    short_pause

    full_summary = ai_summary(summary)
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
    # Indefinite wait — the user may step away to review before clicking
    # Publish. 24h is long enough to act as "indefinite" for any real
    # session while still guaranteeing the process eventually exits.
    new_zid = poll_until(timeout: 86_400, interval: 3, waiting_for: 'publish') do
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

  # After publishing a new Z14 implementation, Wikifunctions does not
  # auto-connect it to its function — the user has to toggle "connected"
  # in the implementations table on the function page. Until then the
  # runtime raises Z503 (no implementation). Poll the function's Z8K4
  # list until the new impl ZID appears.
  def wait_for_impl_connected(function_zid, impl_zid)
    wait_for_function_field(function_zid, 'Z8K4', impl_zid, 'implementation')
  end

  # Same story for testers — they land in Z8K3 only when toggled connected
  # on the function's testers table.
  def wait_for_tester_connected(function_zid, tester_zid)
    wait_for_function_field(function_zid, 'Z8K3', tester_zid, 'tester')
  end

  def wait_for_function_field(function_zid, field, wanted_zid, noun)
    return unless function_zid && wanted_zid

    log ''
    log "Waiting for #{wanted_zid} to be connected to #{function_zid}..."
    log "  (Toggle 'connected' on the #{noun}s table for #{function_zid}.)"

    poll_until(timeout: 86_400, interval: 5, waiting_for: "#{noun} connection") do
      uri = URI(WF_API)
      uri.query = URI.encode_www_form(
        action: 'wikilambda_fetch', zids: function_zid, format: 'json'
      )
      data = JSON.parse(Net::HTTP.get(uri))
      raw = data.dig(function_zid, 'wikilambda_fetch')
      next nil unless raw

      zobj = raw.is_a?(String) ? JSON.parse(raw) : raw
      entries = zobj.dig('Z2K2', field) || []
      entries.include?(wanted_zid) ? true : nil
    end
    log "  Connected."
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

  def select_in_lookup(element_id, zid, label: nil)
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
    label ||= @api_info.dig(zid, :name).to_s

    # Pre-populated Z7K1 slots (auto-selected by type compatibility) are the
    # hard case. `.clear` leaves the underlying Vue/Codex component state in
    # place, so newly-typed characters get appended (e.g. "Z22696Z33071"),
    # which matches no suggestion and the fallback picks a wrong function.
    # We clear with a multi-pronged approach: click to focus, remove any
    # chip, JS-nullify value with synthetic input/change events, and
    # select-all + backspace.
    clear_lookup_field(container, input)
    input.send_keys(zid)

    # Wait for the menu to render a matching suggestion, then click it
    # natively. Two things had to change together:
    # - `dispatchEvent(new MouseEvent)` doesn't commit Codex menu selections
    #   (same story as switch_mode); use Selenium's native click instead.
    # - A fixed `sleep 2` was sometimes too short after the clear/scroll
    #   sequence; retrying in a wait.until handles variable menu-render
    #   latency without over-sleeping on the fast path.
    matched = nil
    begin
      slow_wait(tag: "lookup-#{zid}") do
        # Don't filter by `.displayed?` — Selenium treats items scrolled out
        # of a scrollable dropdown as not displayed, so the screenshot-
        # visible items are often only the first N of many. Scroll+native
        # click (below) will bring the real match into view.
        # Match by ZID-in-text OR the function's label prefix: some menu
        # renders include "(Z#####)" in the text, others only show the
        # label. Label-prefix (not substring) avoids collisions between
        # functions whose labels share a prefix.
        matched = @driver.find_elements(css: '.cdx-menu-item').find do |i|
          txt = (i.text.to_s rescue '')
          next false if txt.empty?

          txt.include?(zid) || (!label.empty? && txt.start_with?(label))
        end
        matched
      end
    rescue Selenium::WebDriver::Error::TimeoutError
      matched = nil
      # Log menu items that actually have text — the DOM has many collapsed
      # menus (mode selectors, etc.) whose items are empty when closed.
      items = @driver.find_elements(css: '.cdx-menu-item')
      with_text = items.filter_map do |i|
        txt = (i.text.to_s.strip.gsub("\n", ' | '))[0, 120]
        txt.empty? ? nil : txt
      end
      log "    menu items with text at timeout (#{with_text.size} of #{items.size}):"
      with_text.first(20).each { |t| log "      #{t.inspect}" }
    end

    if matched
      log "    matched menu item: #{matched.text.to_s.strip.gsub("\n", ' | ')[0, 80].inspect}"
      scroll_to(matched)
      begin
        matched.click
      rescue Selenium::WebDriver::Error::ElementNotInteractableError,
             Selenium::WebDriver::Error::ElementClickInterceptedError
        @driver.execute_script('arguments[0].click()', matched)
      end
    else
      log "    WARNING: no menu item matched #{zid} — aborting (fallback would pick wrong function)"
      raise "select_in_lookup could not find #{zid} in the menu"
    end
    short_pause
  end

  def clear_lookup_field(container, input)
    # 1. Click any chip-remove button in the container. Vue-backed Codex
    #    lookups render a selected value as a chip with an X close button;
    #    `.clear` on the input does not remove the chip.
    selectors = [
      '.cdx-chip-input__remove-button',
      '.cdx-chip__close',
      '.cdx-chip__icon--remove',
      'button[aria-label*="emove"]',
      'button[aria-label*="lear"]'
    ]
    container.find_elements(css: selectors.join(', ')).each do |btn|
      begin
        btn.click if btn.displayed?
      rescue StandardError
        # best effort
      end
    end
    short_pause

    # 2. Focus the input so keyboard events go to the right place.
    begin
      input.click
    rescue StandardError
      # already focused, or intercepted — we'll still try to clear
    end

    # 3. JS-nullify the value and dispatch input/change events so Vue's
    #    v-model updates. This is the only path that reliably resets
    #    internal component state when .clear + chip-close both fail.
    @driver.execute_script(<<~JS, input)
      const el = arguments[0];
      el.focus();
      el.value = '';
      el.dispatchEvent(new Event('input',  { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    JS

    # 4. Select-all + backspace as a belt-and-suspenders keyboard clear.
    input.send_keys([:control, 'a'])
    input.send_keys(:backspace)
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

    # Click the matching menu item natively. `dispatchEvent(new MouseEvent)`
    # doesn't drive Codex's Vue `select-item` pipeline — the menu closed but
    # no selection committed, leaving the field in its original literal mode
    # even though the script proceeded as if switched.
    # Match by the `type` attribute (Z7/Z9/Z18) — precise and i18n-proof.
    slow_wait(tag: "mode-switch-#{mode_value}") do
      item = @driver.find_elements(css: ".cdx-menu-item[type='#{mode_value}']")
                    .find { |i| i.displayed? rescue false }
      next false unless item

      scroll_to(item)
      item.click
      true
    end
    short_pause
  end

  # ── UI primitives: expand/collapse ───────────────────────────

  def expand_at(keypath)
    el = @driver.find_element(id: keypath)
    toggle = el.find_elements(css: '[data-testid="expanded-toggle"]').first
    return unless toggle
    return unless toggle.displayed? rescue false
    # `disabled` means this is a leaf with nothing to expand.
    return if toggle.attribute('disabled')

    # Only expand when currently collapsed — avoid toggling an already-
    # expanded slot back to collapsed. Works uniformly for Z7 / Z18 / Z9 /
    # literal slots (all share the same toggle with `…--collapsed` icon
    # class when shut).
    collapsed = toggle.find_elements(
      css: '.ext-wikilambda-app-expanded-toggle__icon--collapsed'
    ).first
    return unless collapsed

    scroll_to(toggle)
    short_pause
    toggle.click
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

    # Scope to the Z18K1 sub-slot. After switching a slot to Z18 mode, the
    # original literal inputs (e.g., a Wikidata item lookup with role=
    # "combobox") can linger hidden in the DOM, and a broader selector may
    # grab the wrong element.
    #
    # Diag: log the actual child IDs so we know what to scope to.
    child_ids = @driver.find_elements(css: "[id^='#{keypath}-']").map { |e| e.attribute('id') }
    log "    children of #{keypath}: #{child_ids.inspect}"

    z18_slot = @driver.find_elements(id: "#{keypath}-Z18K1").first || el
    handle = z18_slot.find_elements(css: '.cdx-select__handle, [role="combobox"], select')
                     .find { |h| h.displayed? rescue false }
    unless handle
      log "    WARNING: no arg-ref select handle found inside #{keypath}-Z18K1 — aborting"
      raise "select_arg_ref could not find the dropdown handle"
    end

    scroll_to(handle)
    short_pause

    log "    handle tag=<#{handle.tag_name}> " \
        "class=#{handle.attribute('class').to_s[0, 80].inspect} " \
        "role=#{handle.attribute('role').inspect} " \
        "testid=#{handle.attribute('data-testid').inspect}"

    open_codex_select(handle)
    short_pause

    # Click the menu item whose text matches the ref name — more robust
    # than arrow-down counting (which breaks if the dropdown has extra
    # items, or if its open-state pre-highlights one).
    matched = nil
    begin
      slow_wait(tag: "arg-ref-#{ref_name}") do
        matched = @driver.find_elements(css: '.cdx-menu-item')
                         .find { |i| (i.text.to_s.strip.casecmp(ref_name) == 0 rescue false) }
        matched
      end
    rescue Selenium::WebDriver::Error::TimeoutError
      matched = nil
    end

    if matched
      scroll_to(matched)
      begin
        matched.click
      rescue Selenium::WebDriver::Error::ElementNotInteractableError,
             Selenium::WebDriver::Error::ElementClickInterceptedError
        @driver.execute_script('arguments[0].click()', matched)
      end
    else
      log "    WARNING: arg-ref dropdown did not contain '#{ref_name}' — aborting"
      raise "select_arg_ref could not find '#{ref_name}'"
    end
  end

  # Try a sequence of strategies to open a Codex select / combobox.
  # Returns when the element appears opened (aria-expanded=true) or after
  # all strategies are exhausted.
  def open_codex_select(handle)
    strategies = [
      -> { @driver.action.move_to(handle).click.perform },
      -> { handle.click },
      -> { @driver.execute_script('arguments[0].click()', handle) },
      -> {
        @driver.execute_script('arguments[0].focus()', handle)
        sleep 0.1
        handle.send_keys(:space)
      },
      -> {
        @driver.execute_script('arguments[0].focus()', handle)
        sleep 0.1
        handle.send_keys(:enter)
      }
    ]

    strategies.each_with_index do |try, idx|
      begin
        try.call
      rescue StandardError
        next
      end
      sleep 0.15
      if handle.attribute('aria-expanded') == 'true'
        log "    (select opened via strategy #{idx + 1})" if idx.positive?
        return true
      end
    end
    log '    WARNING: select did not open via any strategy'
    false
  end

  # ── UI primitives: literal values ────────────────────────────

  def fill_literal(keypath, value, type, label: nil)
    el = @driver.find_element(id: keypath)

    case type
    when 'Z9' # Reference to a persistent ZObject (e.g. Z1002 for English)
      # The slot is a typed picker (e.g. a "Select language" Codex lookup
      # for Z60). Typing the ZID alone often doesn't filter — the picker
      # indexes by human name — so prefer the human-readable label when
      # the spec provides one, and still match the dropdown by ZID in the
      # item's text (dropdown items usually include "(Z####)").
      input = el.find_elements(css: 'input.cdx-text-input__input, input[type="text"]')
                .find { |i| i.displayed? rescue false }
      raise "fill_literal (Z9): no visible input in #{keypath}" unless input

      scroll_to(input)
      short_pause
      @driver.action.move_to(input).click.perform
      short_pause
      typed = (label && !label.empty?) ? label : value
      @driver.action.send_keys(typed).perform
      short_pause

      # Match priority: ZID in text (most specific, e.g. "English (Z1002)")
      # > exact-label first-line (e.g. "English"). Substring-label match is
      # unsafe here: "Australian English (English)" contains "English" and
      # would be wrongly preferred over plain "English" (Z1002).
      matched = nil
      begin
        slow_wait(timeout: 6, tag: "literal-ref-#{value}") do
          items = @driver.find_elements(css: '.cdx-menu-item')
          matched = items.find do |i|
            (i.text.to_s.include?(value) rescue false)
          end
          if !matched && label && !label.empty?
            matched = items.find do |i|
              txt = (i.text.to_s rescue '')
              next false if txt.empty?

              first_line = txt.split("\n", 2).first.to_s
              first_line == label
            end
          end
          matched
        end
      rescue Selenium::WebDriver::Error::TimeoutError
        matched = nil
        items = @driver.find_elements(css: '.cdx-menu-item')
                       .filter_map { |i| t = (i.text.to_s.strip rescue ''); t.empty? ? nil : t }
        log "    menu items at timeout (#{items.size}): #{items.first(10).map { |t| t[0, 60] }.inspect}"
      end

      if matched
        log "    matched menu item: #{matched.text.to_s.strip[0, 80].inspect}"
        scroll_to(matched)
        begin
          matched.click
        rescue StandardError
          @driver.execute_script('arguments[0].click()', matched)
        end
      else
        raise "fill_literal (Z9): no menu match for #{value.inspect} (typed #{typed.inspect})"
      end

    when 'Z6092', 'Z6091' # Wikidata property or item reference
      # Scope to the value sub-slot (-Z6092K1 / -Z6091K1). The slot's
      # top-level contains a Z1K1 type-marker display with its own input;
      # filling that instead of the value field is what was stuffing
      # "P5137" into the "type" row.
      value_slot = @driver.find_elements(id: "#{keypath}-#{type}K1").first || el
      input = value_slot.find_elements(css: [
        '[data-testid="wikidata-entity-selector"] input.cdx-text-input__input',
        'input.cdx-text-input__input'
      ].join(', ')).find { |i| i.displayed? rescue false }
      unless input
        raise "fill_literal (#{type}): no visible input in #{keypath}-#{type}K1"
      end

      scroll_to(input)
      short_pause

      # ActionChains drives real browser-level pointer+keyboard events,
      # avoiding Selenium's interactability check on Codex inputs.
      @driver.action.move_to(input).click.perform
      short_pause
      @driver.action.send_keys(value).perform
      short_pause

      # If an autocomplete dropdown opens, pick the match; if not, the raw
      # P/Q-number in the input is resolved by Wikifunctions at publish
      # time. Don't raise if no menu appears — empty is valid here.
      begin
        matched = nil
        slow_wait(timeout: 3, tag: "literal-#{value}") do
          matched = @driver.find_elements(css: '.cdx-menu-item').find do |i|
            (i.text.to_s.include?(value) rescue false)
          end
          matched
        end
        if matched
          log "    matched menu item: #{matched.text.to_s.strip[0, 80].inspect}"
          scroll_to(matched)
          begin
            matched.click
          rescue StandardError
            @driver.execute_script('arguments[0].click()', matched)
          end
        end
      rescue Selenium::WebDriver::Error::TimeoutError
        log "    (no autocomplete dropdown — leaving raw value in the field)"
      end

    when 'Z16683' # Integer — expanded slot has sign (Z16659) + absolute value (Z13518).
      fill_integer_literal(keypath, value)

    when 'Z6', 'Z13518' # String, Natural Number — single text input
      input = el.find_elements(css: '[data-testid="text-input"], input.cdx-text-input__input, input[type="number"], input')
                .find { |i| i.displayed? rescue false }
      raise "fill_literal (#{type}): no visible input in #{keypath}" unless input

      input.send_keys([:control, 'a'])
      input.send_keys(:backspace)
      input.send_keys(value)

    else
      log "    WARNING: unknown literal type #{type} -- trying text input"
      begin
        input = el.find_elements(css: 'input').find { |i| i.displayed? rescue false }
        if input
          input.send_keys([:control, 'a'])
          input.send_keys(:backspace)
          input.send_keys(value)
        else
          log '    Could not find a visible input. Set this value manually.'
        end
      rescue Selenium::WebDriver::Error::NoSuchElementError
        log '    Could not find an input. Set this value manually.'
      end
    end
  end

  # Z16683 integer literals render as an expanded composite in the UI:
  # a sign dropdown (Z16659 → Z16660 positive / Z16662 negative / Z16661
  # neutral) and an absolute-value text input (Z13518). A single "type
  # the number" input doesn't exist.
  def fill_integer_literal(keypath, value)
    value_str = value.to_s.strip
    raise "fill_integer_literal: #{value.inspect} is not a valid integer" unless value_str.match?(/\A[+-]?\d+\z/)

    n = value_str.to_i
    abs_str = n.abs.to_s
    sign_label = n.positive? ? 'positive' : (n.negative? ? 'negative' : 'neutral')

    # Sign dropdown (Z16683K1 → Z16659).
    sign_slot = @driver.find_elements(id: "#{keypath}-Z16683K1").first
    if sign_slot
      handle = sign_slot.find_elements(css: '.cdx-select-vue__handle, [role="combobox"]')
                        .find { |h| h.displayed? rescue false }
      if handle
        scroll_to(handle)
        short_pause
        open_codex_select(handle)
        short_pause
        match = @driver.find_elements(css: '.cdx-menu-item').find do |i|
          first_line = (i.text.to_s.split("\n", 2).first || '').strip.downcase
          first_line == sign_label
        end
        if match
          scroll_to(match)
          begin
            match.click
          rescue StandardError
            @driver.execute_script('arguments[0].click()', match)
          end
        else
          log "    WARNING: no sign menu item matched #{sign_label.inspect}"
        end
      end
    end
    short_pause

    # Absolute value text input (Z16683K2 → Z13518).
    abs_slot = @driver.find_elements(id: "#{keypath}-Z16683K2").first || @driver.find_element(id: keypath)
    abs_input = abs_slot.find_elements(css: 'input.cdx-text-input__input, input[type="text"], input[type="number"]')
                        .find { |i| i.displayed? rescue false }
    raise "fill_integer_literal: no visible absolute-value input under #{keypath}" unless abs_input

    scroll_to(abs_input)
    short_pause
    @driver.action.move_to(abs_input).click.perform
    short_pause
    @driver.action.send_keys(abs_str).perform
    short_pause
  end

  # ── Raw-JSON userscript driver ───────────────────────────────
  # Works with userscripts/wikilambda-edit-source.js. We drive the
  # userscript's editor rather than POST directly so the user sees
  # exactly what's being saved and clicks Save themselves.

  def wait_for_raw_json_userscript
    slow_wait(tag: 'userscript-load', timeout: 15) do
      @driver.execute_script(
        'return !!document.getElementById("pt-wf-raw-json-create")'
      )
    end
  rescue Selenium::WebDriver::Error::TimeoutError
    raise 'Raw-JSON userscript did not load. Install ' \
          'userscripts/wikilambda-edit-source.js in your Wikifunctions common.js.'
  end

  def click_raw_json_portlet(kind)
    id = kind == :edit ? 'pt-wf-raw-json-edit' : 'pt-wf-raw-json-create'
    portlet = @driver.find_element(id: id)
    scroll_to(portlet)
    short_pause
    portlet.click
  end

  def wait_for_raw_json_textarea
    slow_wait(tag: 'raw-json-textarea') { safe_find('#wf-raw-json-textarea') }
  end

  # Selenium's .clear + .send_keys is slow and event-fragile for large
  # JSON blobs; setting .value directly + dispatching the events the
  # userscript (and the "no changes" guard) rely on is faster and more
  # reliable.
  def set_textarea_value(el, value)
    @driver.execute_script(<<~JS, el, value)
      const el = arguments[0];
      const value = arguments[1];
      el.focus();
      el.value = value;
      el.dispatchEvent(new Event('input',  { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    JS
  end

  def fill_raw_json_summary(summary)
    input = @driver.find_element(id: 'wf-raw-json-summary')
    input.clear
    input.send_keys(summary)
  end

  # Edit flow: navigate to the target Z-page, click Edit Raw JSON,
  # wait for the userscript's fetch-populated textarea, yield the
  # parsed JSON for the caller to mutate, then write the mutated
  # result back and fill the summary. Does NOT click Save — the
  # user reviews and saves themselves.
  def drive_raw_json_edit(zid:, summary:)
    navigate_to("#{WF_BASE}/wiki/#{zid}")
    wait_for_raw_json_userscript
    step "Opening Edit Raw JSON for #{zid}..."
    click_raw_json_portlet(:edit)
    textarea = wait_for_raw_json_textarea
    current = textarea.attribute('value').to_s
    raise "Edit Raw JSON: textarea empty for #{zid}" if current.empty?

    parsed = JSON.parse(current)
    modified = yield(parsed)
    set_textarea_value(textarea, JSON.pretty_generate(modified))
    fill_raw_json_summary(summary)
  end

  # Create flow: navigate to a context page (the function we're
  # adding to, if known), click Create Raw JSON, fill the textarea
  # with our pre-built Z2 JSON and fill the summary. Does NOT click
  # Save.
  def drive_raw_json_create(zobject_json:, summary:, landing_zid: nil)
    landing = landing_zid ? "#{WF_BASE}/wiki/#{landing_zid}" : WF_BASE
    navigate_to(landing)
    wait_for_raw_json_userscript
    step 'Opening Create Raw JSON...'
    click_raw_json_portlet(:create)
    textarea = wait_for_raw_json_textarea
    set_textarea_value(textarea, zobject_json)
    fill_raw_json_summary(summary)
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
    sleep [@delay * 0.4, 0.15].max
  end

  # ── Helpers ──────────────────────────────────────────────────

  # Raises if another browser is still running with this profile.
  # Chrome's SingletonLock and Firefox's `lock` are symlinks whose target
  # encodes the owning PID; if the PID is alive, launching a second instance
  # would corrupt session state (this is how we lost the login earlier).
  def ensure_profile_free!
    pid = owning_pid
    return unless pid

    raise "#{@browser.to_s.capitalize} is already running with this profile " \
          "(PID #{pid}).\n" \
          "  Profile: #{PROFILE_DIR}\n" \
          "Close the browser window or `kill #{pid}`, then retry."
  end

  def owning_pid
    case @browser
    when :chrome  then chrome_owning_pid
    when :firefox then firefox_owning_pid
    end
  end

  def chrome_owning_pid
    # SingletonLock is a symlink pointing to "<hostname>-<pid>".
    link = File.join(PROFILE_DIR, 'SingletonLock')
    return nil unless File.symlink?(link)

    target = File.readlink(link) rescue nil
    pid = target&.rpartition('-')&.last.to_i
    process_alive?(pid) ? pid : nil
  end

  def firefox_owning_pid
    # Firefox's `lock` symlink target is "<ip>:+<pid>" on Linux.
    link = File.join(PROFILE_DIR, 'lock')
    return nil unless File.symlink?(link)

    target = File.readlink(link) rescue nil
    pid = target&.rpartition('+')&.last.to_i
    process_alive?(pid) ? pid : nil
  end

  def process_alive?(pid)
    return false if pid.nil? || pid <= 0

    Process.kill(0, pid)
    true
  rescue Errno::ESRCH
    false
  rescue Errno::EPERM
    # PID exists but we don't own it — still treat as live (not ours to steal).
    true
  end

  # Like Wait.until but snaps a screenshot if we end up waiting past
  # `slow_after` seconds — which in practice means something went sideways,
  # because the happy-path steps all complete in well under a second. We
  # cap at 10s by default: if a step hasn't succeeded by then, bail with a
  # screenshot rather than letting a broken UI path stall the whole run.
  def slow_wait(timeout: 10, slow_after: 4, tag: 'wait', interval: 0.15)
    start = Time.now
    shot = false
    loop do
      result = yield
      return result if result

      elapsed = Time.now - start
      if !shot && elapsed > slow_after
        save_debug_screenshot(tag)
        shot = true
      end
      if elapsed > timeout
        save_debug_screenshot("#{tag}-final") unless shot
        raise Selenium::WebDriver::Error::TimeoutError,
              "slow_wait timed out after #{timeout}s: #{tag}"
      end
      sleep interval
    end
  end

  def save_debug_screenshot(tag)
    ts = Time.now.strftime('%H%M%S')
    safe_tag = tag.to_s.gsub(/[^A-Za-z0-9_-]/, '_')
    path = "/tmp/wf-stuck-#{safe_tag}-#{ts}.png"
    @driver.save_screenshot(path)
    log "  screenshot: #{path}"
  rescue StandardError => e
    log "  (screenshot failed: #{e.message})"
  end

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
    slow_wait(tag: 'mw-config-load') do
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
