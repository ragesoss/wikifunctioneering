# frozen_string_literal: true

# Shared ZObject-tree build logic for any task that constructs a Z7-rooted
# composition in the UI (compositions, testers, etc.).
#
# Including classes must provide:
#   - `@wf`   — the WfBrowser instance
#   - `@spec` — the task spec hash (optional; only `func_name` / `arg_label_for`
#               use node-level `name` / `label` hints, which come from each
#               node itself)

module WfCompositionBuilder
  private

  def collect_call_zids(node)
    return [] unless node.is_a?(Hash) && node['call']

    [node['call']] + (node['args'] || {}).values.flat_map { |v| collect_call_zids(v) }
  end

  def build_function_call(node, keypath)
    zid = node['call']
    args = node['args'] || {}

    first_arg_id = args.any? ? "#{keypath}-#{args.keys.first}" : nil
    already_selected = first_arg_id && @wf.safe_find("[id='#{first_arg_id}']")

    if already_selected
      @wf.step "Select function: #{zid} (#{func_name(zid, node)}) — already pre-selected"
    else
      @wf.step "Select function: #{zid} (#{func_name(zid, node)})"
      @wf.select_in_lookup("#{keypath}-Z7K1", zid, label: @wf.api_info.dig(zid, :name))
      @wf.pause

      return if args.empty?

      @wf.log '  Waiting for argument fields...'
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
      @wf.fill_literal(keypath, node['literal'], node['type'], label: node['label'])
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
