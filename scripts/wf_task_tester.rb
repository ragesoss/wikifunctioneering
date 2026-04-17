# frozen_string_literal: true

# Task: edit an existing tester (Z20) on Wikifunctions.
#
# A tester has three fields:
#   - Z20K1: the function being tested
#   - Z20K2: the test call (a Z7 tree that invokes the function)
#   - Z20K3: the validator (a Z7 tree taking the function's output as its
#            first argument, returning Z40 true/false)
#
# Spec format (edit a tester):
#   {
#     "task": "tester",
#     "tester_zid": "Z26185",
#     "function_zid": "Z26184",
#     "label": "do -> sa",
#     "summary": "Use case-insensitive string equality",
#     "validator": {
#       "call": "Z10539",
#       "args": {
#         "Z10539K2": {"literal": "Sa", "type": "Z6"}
#       }
#     }
#     // test_call is optional; omit to leave it unchanged
#   }
#
# Creation of brand-new testers isn't supported yet — add it when needed.

require_relative 'wf_browser'
require_relative 'wf_composition_builder'

class WfTaskTester
  include WfCompositionBuilder

  def initialize(wf, spec)
    @wf = wf
    @spec = spec
  end

  def run
    raise 'tester task requires "tester_zid" (creation not yet supported)' unless @spec['tester_zid']

    @wf.set_function_zid(@spec['function_zid']) if @spec['function_zid']
    navigate_to_edit(@spec['tester_zid'])
    fetch_metadata

    @wf.set_label(@spec['label']) if @spec['label']

    build_subtree('Z20K2', @spec['test_call']) if @spec['test_call']
    build_subtree('Z20K3', @spec['validator']) if @spec['validator']

    @wf.open_publish_dialog(@spec['summary'])
    @wf.verify_published
  end

  private

  def navigate_to_edit(tester_zid)
    url = "#{WfBrowser::WF_BASE}/view/en/#{tester_zid}"
    @wf.step "Opening tester page: #{url}"
    @wf.navigate_to(url)

    @wf.log '  Waiting for page to load...'
    @wf.slow_wait(tag: 'tester-page-load') { @wf.safe_find('.ext-wikilambda-app') }
    @wf.pause

    @wf.click_edit_source

    @wf.log '  Waiting for tester editor...'
    @wf.slow_wait(tag: 'tester-edit-mode') do
      @wf.driver.find_elements(css: '[id*="-Z20K2"], [id*="-Z20K3"]').any?
    end
    @wf.log '  Edit mode ready.'
    @wf.pause
  end

  def fetch_metadata
    zids = [@wf.function_zid].compact
    zids += collect_call_zids(@spec['test_call'])
    zids += collect_call_zids(@spec['validator'])
    @wf.fetch_metadata_for(zids.uniq)
  end

  # Locate the Z20K2 / Z20K3 subtree's root Z7K1 keypath, then delegate to
  # WfCompositionBuilder#build_function_call. Reuses the same node-tree
  # format (call / ref / literal) as the composition task.
  def build_subtree(z20_field, node)
    @wf.step "Building #{z20_field} (#{human_field(z20_field)})"

    prefix = find_subtree_prefix(z20_field)
    @wf.log "  #{z20_field} keypath prefix: #{prefix}"

    build_function_call(node, prefix)
  end

  def find_subtree_prefix(z20_field)
    # Each Z20Kx row renders collapsed (compact link like `string
    # equality("Sa")`) in edit mode — expand it so the inner Z7K1 key/value
    # block shows up in the DOM.
    outer = @wf.driver.find_elements(css: "[id$='-#{z20_field}']")
                      .find { |el| el.attribute('class')&.include?('object-key-value') }
    raise "No #{z20_field} container found on this page" unless outer

    @wf.expand_at(outer.attribute('id'))
    @wf.short_pause

    z7k1 = @wf.slow_wait(tag: "find-#{z20_field}") do
      outer.find_elements(css: "[id$='-Z7K1']")
           .find { |el| el.attribute('class')&.include?('object-key-value') }
    end
    z7k1.attribute('id').sub(/-Z7K1$/, '')
  end

  def human_field(z20_field)
    case z20_field
    when 'Z20K2' then 'test call'
    when 'Z20K3' then 'validator'
    else z20_field
    end
  end
end
