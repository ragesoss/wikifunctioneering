# frozen_string_literal: true

# Task: create a function shell on Wikifunctions.
#
# Spec format:
#   {
#     "task": "function",
#     "label": "MIDI number of pitch",
#     "description": "Computes MIDI note number from pitch class and octave",
#     "inputs": [
#       {"label": "pitch class", "type": "Z6"},
#       {"label": "octave", "type": "Z16683"}
#     ],
#     "output_type": "Z16683",
#     "summary": "New function for pitch standard pipeline"
#   }

require_relative 'wf_browser'

class WfTaskFunction
  def initialize(wf, spec)
    @wf = wf
    @spec = spec
  end

  def run
    navigate_to_create_function
    set_name
    set_description
    set_inputs
    set_output_type
    @wf.open_publish_dialog(@spec['summary'])
    @wf.verify_published
  end

  private

  def navigate_to_create_function
    url = "#{WfBrowser::WF_BASE}/w/index.php?title=Special:CreateObject&uselang=en&zid=Z8"
    @wf.step "Opening function creation page: #{url}"
    @wf.navigate_to(url)

    @wf.log '  Waiting for page to load...'
    @wf.slow_wait(tag: 'function-editor-page-load') { @wf.safe_find('[data-testid="function-editor-definition"]') }
    @wf.log '  Page ready.'
    @wf.pause
  end

  def set_name
    return unless @spec['label']

    @wf.step "Setting name: #{@spec['label']}"
    input = @wf.driver.find_element(
      css: '[data-testid="function-editor-name-input"] input.cdx-text-input__input'
    )
    @wf.scroll_to(input)
    @wf.short_pause
    input.clear
    input.send_keys(@spec['label'])
    @wf.pause
  end

  def set_description
    return unless @spec['description']

    @wf.step "Setting description: #{@spec['description']}"
    textarea = @wf.driver.find_element(
      css: '[data-testid="function-editor-description-input"] textarea'
    )
    @wf.scroll_to(textarea)
    @wf.short_pause
    textarea.clear
    textarea.send_keys(@spec['description'])
    @wf.pause
  end

  def set_inputs
    inputs = @spec['inputs'] || []

    inputs.each_with_index do |input_spec, i|
      @wf.step "Setting input #{i + 1}: #{input_spec['label']} (#{input_spec['type']})"

      # The page starts with one empty input slot. For additional inputs,
      # click the "Add another input" button. Filter by text because the
      # button has no testid and the inputs container also holds per-slot
      # "Remove input" buttons.
      if i > 0
        add_btn = @wf.driver.find_elements(css: '[data-testid="function-editor-inputs"] button')
                       .find { |b| (b.displayed? rescue false) && b.text.strip.match?(/^Add/i) }
        if add_btn
          @wf.scroll_to(add_btn)
          @wf.short_pause
          add_btn.click
          @wf.pause
        else
          @wf.log "    WARNING: could not find 'Add another input' button."
        end
      end

      # Find the input items. Take the last one (newest).
      input_items = @wf.driver.find_elements(css: '[data-testid="function-editor-input-item"]')
      item = input_items.last
      unless item
        @wf.log "    WARNING: no input item found — set manually."
        next
      end

      # Set the label
      label_input = item.find_element(css: '[data-testid="function-editor-input-item-label"] input')
      @wf.scroll_to(label_input)
      @wf.short_pause
      label_input.clear
      label_input.send_keys(input_spec['label'])
      @wf.pause

      # Set the type via the lookup
      type_input = item.find_element(css: '[data-testid="function-editor-input-item-type"] input.cdx-text-input__input')
      @wf.scroll_to(type_input)
      @wf.short_pause
      type_input.clear
      type_input.send_keys(input_spec['type'])
      sleep 2
      type_input.send_keys(:arrow_down)
      @wf.short_pause
      type_input.send_keys(:return)
      @wf.pause
    end
  end

  def set_output_type
    return unless @spec['output_type']

    @wf.step "Setting output type: #{@spec['output_type']}"
    output_input = @wf.driver.find_element(
      css: '[data-testid="function-editor-output-type"] input.cdx-text-input__input'
    )
    @wf.scroll_to(output_input)
    @wf.short_pause
    output_input.clear
    output_input.send_keys(@spec['output_type'])
    sleep 2
    output_input.send_keys(:arrow_down)
    @wf.short_pause
    output_input.send_keys(:return)
    @wf.pause
  end
end
