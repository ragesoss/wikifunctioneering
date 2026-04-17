# frozen_string_literal: true

# Emit canonical ZObject JSON from the same spec-tree format that
# WfCompositionBuilder walks to drive the UI. This is the API-mode
# equivalent of clicking — given a node tree and the function's
# argument metadata, produce a server-ready ZObject.
#
# Node types:
#   {"call": "Z##", "args": {"Z##K#": <node>, ...}}  -> Z7 function call
#   {"ref": "arg name"}                              -> Z18 argument reference
#   {"literal": "val", "type": "Z##"}                -> typed literal
#
# Z18 refs resolve against `function_zid`'s arguments — the top-level
# function the composition / tester belongs to. This matches the UI's
# behavior (see WfBrowser#select_arg_ref).

module WfZObjectEmitter
  # Z16659 (Sign) values. See CLAUDE.md.
  SIGN_POS = 'Z16660'
  SIGN_ZERO = 'Z16661'
  SIGN_NEG = 'Z16662'

  module_function

  def emit(node, function_zid:, api_info:)
    unless node.is_a?(Hash)
      raise "wf_zobject_emitter: node must be a Hash, got #{node.class}: #{node.inspect}"
    end

    if node['call']
      emit_call(node, function_zid: function_zid, api_info: api_info)
    elsif node['ref']
      emit_ref(node, function_zid: function_zid, api_info: api_info)
    elsif node.key?('literal')
      emit_literal(node)
    else
      raise "wf_zobject_emitter: node has no call/ref/literal key: #{node.inspect}"
    end
  end

  def emit_call(node, function_zid:, api_info:)
    zid = node['call']
    args = node['args'] || {}
    result = { 'Z1K1' => 'Z7', 'Z7K1' => zid }
    args.each do |arg_key, arg_node|
      result[arg_key] = emit(arg_node, function_zid: function_zid, api_info: api_info)
    end
    result
  end

  def emit_ref(node, function_zid:, api_info:)
    ref_name = node['ref']
    args = api_info.dig(function_zid, :args) || {}
    arg_key = args.find { |_k, v| v.to_s.downcase == ref_name.to_s.downcase }&.first
    unless arg_key
      raise "wf_zobject_emitter: no argument '#{ref_name}' on #{function_zid} " \
            "(available: #{args.values.inspect})"
    end

    { 'Z1K1' => 'Z18', 'Z18K1' => arg_key }
  end

  def emit_literal(node)
    value = node['literal']
    type = node['type']
    raise "emit_literal: node has no type: #{node.inspect}" unless type

    case type
    when 'Z6'
      { 'Z1K1' => 'Z6', 'Z6K1' => value.to_s }
    when 'Z9'
      # Canonical form stores Z9 references as bare strings (this is what
      # we observe in the ?action=raw body).
      value.to_s
    when 'Z6091', 'Z6092'
      { 'Z1K1' => type, "#{type}K1" => value.to_s }
    when 'Z13518'
      { 'Z1K1' => 'Z13518', 'Z13518K1' => value.to_s }
    when 'Z16683'
      emit_integer_literal(value)
    when 'Z20838'
      # Float64 has an IEEE-754 substructure that's brittle to emit by
      # hand. Wrap a Z6 string with Z20915 (string to float64) in the
      # spec instead — same convention as CLAUDE.md's tester examples.
      raise 'emit_literal: Z20838 (float64) should be produced by a ' \
            'Z20915 "string to float64" call, not a raw literal. ' \
            'Change the spec node to {"call": "Z20915", "args": {' \
            '"Z20915K1": {"literal": "' + value.to_s + '", "type": "Z6"}}}.'
    else
      raise "emit_literal: unsupported literal type #{type.inspect}"
    end
  end

  # Build a fresh Z2 persistent-object wrapper around `content`. Used
  # by API create paths. Z2K1 uses the Z0 placeholder; the server
  # assigns the real ZID on save.
  def new_persistent(content, label: nil)
    z2 = {
      'Z1K1' => 'Z2',
      'Z2K1' => { 'Z1K1' => 'Z6', 'Z6K1' => 'Z0' },
      'Z2K2' => content,
      'Z2K3' => { 'Z1K1' => 'Z12', 'Z12K1' => ['Z11'] },
      'Z2K4' => { 'Z1K1' => 'Z32', 'Z32K1' => ['Z31'] },
      'Z2K5' => { 'Z1K1' => 'Z12', 'Z12K1' => ['Z11'] }
    }
    set_en_label!(z2['Z2K3'], label) if label
    z2
  end

  # Update or append the English monolingual entry in a Z12 multilingual
  # string. Mutates `z12` in place; also returns it. The list-head type
  # marker at index 0 ("Z11") is preserved.
  def set_en_label!(z12, label)
    z12['Z1K1'] ||= 'Z12'
    entries = z12['Z12K1'] ||= ['Z11']
    en_entry = entries[1..].find { |e| e.is_a?(Hash) && e['Z11K1'] == 'Z1002' }
    if en_entry
      en_entry['Z11K2'] = label
    else
      entries << { 'Z1K1' => 'Z11', 'Z11K1' => 'Z1002', 'Z11K2' => label }
    end
    z12
  end

  def emit_integer_literal(value)
    s = value.to_s.strip
    unless s.match?(/\A[+-]?\d+\z/)
      raise "emit_integer_literal: #{value.inspect} is not a valid integer"
    end

    n = s.to_i
    sign = if n.positive?
             SIGN_POS
           elsif n.negative?
             SIGN_NEG
           else
             SIGN_ZERO
           end

    {
      'Z1K1' => 'Z16683',
      'Z16683K1' => { 'Z1K1' => 'Z16659', 'Z16659K1' => sign },
      'Z16683K2' => { 'Z1K1' => 'Z13518', 'Z13518K1' => n.abs.to_s }
    }
  end
end
