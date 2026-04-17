# frozen_string_literal: true

# Task: create or edit a composition implementation on Wikifunctions.

require_relative 'wf_browser'

class WfTaskComposition
  def initialize(wf, spec)
    @wf = wf
    @spec = spec
  end

  def run
    if @spec['implementation_zid']
      edit_existing
    elsif @spec['function_zid']
      create_new
    else
      wait_and_create
    end

    @wf.set_label(@spec['label'])
    build_tree
    @wf.open_publish_dialog(@spec['summary'])
    new_zid = @wf.verify_published
    # New implementations come in "disconnected" — wait for the user to
    # toggle "connected" on the function page before reporting done, so
    # the runtime actually uses this impl on the next call.
    @wf.wait_for_impl_connected(@spec['function_zid'], new_zid) if new_zid && @spec['function_zid']
    new_zid
  end

  private

  def create_new
    @wf.set_function_zid(@spec['function_zid'])
    navigate_to_function
    fetch_metadata
    @wf.validate_function(@spec['expect_args'])
    click_add_implementation
  end

  def edit_existing
    @wf.set_function_zid(@spec['function_zid']) if @spec['function_zid']
    navigate_to_edit(@spec['implementation_zid'])
    fetch_metadata
    clear_composition
  end

  def wait_and_create
    wait_for_composition_ui
    fetch_metadata
    @wf.validate_function(@spec['expect_args'])
  end

  # ── Navigation ──

  def navigate_to_function
    url = "#{WfBrowser::WF_BASE}/view/en/#{@wf.function_zid}"
    @wf.step "Opening function page: #{url}"
    @wf.navigate_to(url)

    @wf.log '  Waiting for page to load...'
    @wf.driver.manage.timeouts.implicit_wait = 0
    @wf.slow_wait(tag: 'function-page-load') { @wf.safe_find('[data-testid="function-implementations-table"]') }
    @wf.log "  Function page loaded: #{@wf.function_zid}"
    @wf.pause
  end

  def click_add_implementation
    @wf.step 'Clicking "Add implementation"...'

    add_link = @wf.driver.find_element(
      css: '[data-testid="function-implementations-table"] [data-testid="add-link"]'
    )
    @wf.scroll_to(add_link)
    @wf.short_pause
    add_link.click

    @wf.log '  Waiting for implementation editor...'
    @wf.slow_wait(tag: 'impl-editor-ready') { @wf.safe_find('[data-testid="implementation-radio"]') }
    @wf.log '  Implementation editor ready.'
    @wf.pause
  end

  def navigate_to_edit(impl_zid)
    url = "#{WfBrowser::WF_BASE}/view/en/#{impl_zid}"
    @wf.step "Opening implementation page: #{url}"
    @wf.navigate_to(url)

    @wf.log '  Waiting for page to load...'
    @wf.slow_wait(tag: 'impl-page-load') { @wf.safe_find('.ext-wikilambda-app') }
    @wf.pause

    @wf.click_edit_source

    @wf.log '  Waiting for implementation editor...'
    @wf.slow_wait(tag: 'edit-mode-ready') { @wf.safe_find('[data-testid="implementation-radio"]') }
    @wf.log '  Edit mode ready.'
    @wf.pause
  end

  def wait_for_composition_ui
    @wf.log ''
    @wf.log 'Navigate to the composition editor when ready.'
    @wf.log '  - Open a function, click "Add implementation", or'
    @wf.log '  - Go to Special:CreateObject with zid=Z14'

    zid = @wf.poll_until(timeout: 600, interval: 3, waiting_for: 'composition UI') do
      url = @wf.current_url
      if url.include?('CreateObject') && url =~ /Z14K1=(Z\d+)/
        found = ::Regexp.last_match(1)
        found if @wf.safe_find('[data-testid="implementation-radio"]')
      end
    end

    @wf.set_function_zid(zid)
    @wf.log "Function: #{zid}"
  end

  def clear_composition
    @wf.step 'Clearing existing composition (toggle Code -> Composition)...'

    code_radio = @wf.driver.find_element(
      css: '[data-testid="implementation-radio"] input[value="Z14K3"]'
    )
    @wf.driver.execute_script('arguments[0].click()', code_radio)
    @wf.pause

    comp_radio = @wf.driver.find_element(
      css: '[data-testid="implementation-radio"] input[value="Z14K2"]'
    )
    @wf.driver.execute_script('arguments[0].click()', comp_radio)
    @wf.pause
    @wf.log '  Composition cleared.'
  end

  # ── Metadata ──

  def fetch_metadata
    composition = @spec['composition']
    zids = collect_call_zids(composition) + [@wf.function_zid].compact
    @wf.fetch_metadata_for(zids.uniq)
  end

  def collect_call_zids(node)
    return [] unless node.is_a?(Hash) && node['call']

    [node['call']] + (node['args'] || {}).values.flat_map { |v| collect_call_zids(v) }
  end

  # ── Composition building ──

  def build_tree
    ensure_composition_selected
    expand_root
    build_function_call(@spec['composition'], @prefix)
  end

  def ensure_composition_selected
    radio = @wf.driver.find_element(
      css: '[data-testid="implementation-radio"] input[value="Z14K2"]'
    )
    unless radio.selected?
      @wf.step 'Selecting Composition type'
      @wf.driver.execute_script('arguments[0].click()', radio)
      @wf.pause
    end
  end

  def expand_root
    @wf.step 'Expanding composition root'
    content = @wf.driver.find_element(css: '[data-testid="implementation-content"]')

    2.times do
      z7k1 = @wf.driver.find_elements(css: '[id*="Z14K2"][id*="Z7K1"]')
                        .find { |el| el.attribute('class')&.include?('object-key-value') }
      break if z7k1

      @wf.click_first(content,
                       '[data-testid="object-to-string-link"]',
                       '[data-testid="expanded-toggle"]')
      @wf.pause
    end

    z7k1 = @wf.slow_wait(tag: 'composition-root-expand') do
      @wf.driver.find_elements(css: '[id*="Z14K2"][id*="Z7K1"]')
               .find { |el| el.attribute('class')&.include?('object-key-value') }
    end
    @prefix = z7k1.attribute('id').sub(/-Z7K1$/, '')
    @wf.log "  Keypath prefix: #{@prefix}"
  end

  def build_function_call(node, keypath)
    zid = node['call']
    args = node['args'] || {}

    # Check if the function is already pre-selected (argument fields exist)
    first_arg_id = args.any? ? "#{keypath}-#{args.keys.first}" : nil
    already_selected = first_arg_id && @wf.safe_find("[id='#{first_arg_id}']")

    if already_selected
      @wf.step "Select function: #{zid} (#{func_name(zid, node)}) — already pre-selected"
    else
      @wf.step "Select function: #{zid} (#{func_name(zid, node)})"
      @wf.select_in_lookup("#{keypath}-Z7K1", zid)
      @wf.pause

      return if args.empty?

      @wf.log "  Waiting for argument fields..."
      @wf.slow_wait(tag: "arg-fields-#{zid}") { @wf.safe_find("[id='#{first_arg_id}']") }
    end

    @wf.short_pause

    args.each do |arg_key, arg_node|
      fill_argument(zid, keypath, arg_key, arg_node)
    end
  end

  def fill_argument(parent_zid, parent_keypath, arg_key, node)
    label = arg_label_for(parent_zid, arg_key, node)
    keypath = "#{parent_keypath}-#{arg_key}"

    # Slots appear collapsed by default after their parent function is
    # selected. Expand up front so the mode selector and inner controls
    # are reachable regardless of which branch we take below.
    @wf.expand_at(keypath)
    @wf.short_pause

    if node['call']
      @wf.step "  #{label} -> function call: #{node['call']} (#{func_name(node['call'], node)})"
      @wf.switch_mode(keypath, 'Z7')
      @wf.pause
      @wf.expand_at(keypath)
      @wf.pause
      build_function_call(node, keypath)

    elsif node['ref']
      @wf.step "  #{label} -> argument reference: #{node['ref']}"
      @wf.switch_mode(keypath, 'Z18')
      @wf.pause
      @wf.expand_at(keypath)
      @wf.pause
      @wf.select_arg_ref(keypath, node['ref'])
      @wf.pause

    elsif node['literal']
      @wf.step "  #{label} -> literal #{node['type']}: #{node['literal']}"
      @wf.expand_at(keypath)
      @wf.pause
      @wf.fill_literal(keypath, node['literal'], node['type'])
      @wf.pause
    end
  end

  def func_name(zid, node = nil)
    node&.dig('name') || @wf.api_info.dig(zid, :name) || zid
  end

  def arg_label_for(parent_zid, arg_key, arg_node)
    arg_node&.dig('label') || @wf.api_info.dig(parent_zid, :args, arg_key) || arg_key
  end
end
