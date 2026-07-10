#!/usr/bin/env ruby
# frozen_string_literal: true

# Emit a server-ready Z2 ZObject JSON from a composition or tester spec,
# WITHOUT a browser. This is the headless counterpart to the wf.rb build
# path: it reuses WfZObjectEmitter (the same emitter the API-mode browser
# route uses) but resolves argument-reference labels via a direct API
# fetch instead of the in-browser metadata cache.
#
# Pipe the output straight into wikifunctions_edit.py:
#   ruby scripts/wf_emit_zobject.rb zobjects/foo.tester.json \
#     | python scripts/wikifunctions_edit.py create --summary "..."
#
# Spec shapes (same as the wf.rb specs):
#   tester       -> function_zid + test_call/validator  => Z20
#   composition  -> function_zid + composition          => Z14
#
# Usage:
#   ruby scripts/wf_emit_zobject.rb SPEC_FILE

require 'json'
require 'net/http'
require 'uri'
require_relative 'wf_zobject_emitter'

WF_API = 'https://www.wikifunctions.org/w/api.php'

# Build { function_zid => { args: { arg_key => label } } } so the emitter
# can resolve {"ref": "label"} nodes to Z18 argument references. Only
# needed when the spec actually contains ref nodes.
def api_info_for(function_zid)
  uri = URI(WF_API)
  uri.query = URI.encode_www_form(
    action: 'wikilambda_fetch', zids: function_zid, format: 'json'
  )
  data = JSON.parse(Net::HTTP.get(uri))
  raw = data.dig(function_zid, 'wikilambda_fetch')
  raise "could not fetch #{function_zid}" unless raw

  zobj = raw.is_a?(String) ? JSON.parse(raw) : raw
  fn = zobj['Z2K2']
  args = {}
  Array(fn['Z8K1'])[1..].to_a.each do |arg|
    key = arg['Z17K2']
    label = Array(arg.dig('Z17K3', 'Z12K1'))[1..].to_a
                 .find { |m| m['Z11K1'] == 'Z1002' }&.dig('Z11K2')
    args[key] = label
  end
  { function_zid => { args: args } }
end

def uses_refs?(node)
  return false unless node.is_a?(Hash)
  return true if node['ref']

  (node['args'] || {}).values.any? { |child| uses_refs?(child) }
end

spec_file = ARGV.shift
abort "Usage: #{$PROGRAM_NAME} SPEC_FILE" unless spec_file
spec = JSON.parse(File.read(spec_file))
function_zid = spec['function_zid']
abort 'spec needs function_zid' unless function_zid

nodes = [spec['composition'], spec['test_call'], spec['validator']].compact
api_info = nodes.any? { |n| uses_refs?(n) } ? api_info_for(function_zid) : {}

content =
  if spec['composition']
    {
      'Z1K1' => 'Z14',
      'Z14K1' => function_zid,
      'Z14K2' => WfZObjectEmitter.emit(
        spec['composition'], function_zid: function_zid, api_info: api_info
      )
    }
  elsif spec['test_call'] || spec['validator']
    c = { 'Z1K1' => 'Z20', 'Z20K1' => function_zid }
    if spec['test_call']
      c['Z20K2'] = WfZObjectEmitter.emit(
        spec['test_call'], function_zid: function_zid, api_info: api_info
      )
    end
    if spec['validator']
      c['Z20K3'] = WfZObjectEmitter.emit(
        spec['validator'], function_zid: function_zid, api_info: api_info
      )
    end
    c
  else
    abort 'spec needs "composition", "test_call", or "validator"'
  end

z2 = WfZObjectEmitter.new_persistent(content, label: spec['label'])
puts JSON.pretty_generate(z2)
