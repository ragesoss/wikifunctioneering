# frozen_string_literal: true

# Task: create or edit a composition implementation on Wikifunctions.

require_relative 'wf_browser'
require_relative 'wf_composition_builder'

class WfTaskComposition
  include WfCompositionBuilder

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

end
