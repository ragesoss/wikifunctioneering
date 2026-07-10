#!/usr/bin/env ruby
# frozen_string_literal: true

# Generate Z20 tester ZObjects for Z18522 "segment sentences" from the
# golden-rules data file (zobjects/sentence_segmentation_golden_rules.json).
#
# Each tester follows the pattern locked in on GR1:
#   Z20K1 = Z18522
#   Z20K2 = Z18522(<input string>)
#   Z20K3 = Z889(  [result auto-binds to Z889K1],
#                  Z889K2 = expected List(Z6),
#                  Z889K3 = Z866 string equality )
# Label = "GR<n> <short concept>" (no theme hook).
#
# Usage:
#   ruby scripts/gen_segmentation_testers.rb --list          # n, label, #sentences
#   ruby scripts/gen_segmentation_testers.rb --rule N        # print Z2 JSON for rule N
#   ruby scripts/gen_segmentation_testers.rb --validate      # build all, assert well-formed

require 'json'
require_relative 'wf_zobject_emitter'

DATA = File.expand_path('../../zobjects/sentence_segmentation_golden_rules.json', __FILE__)
TARGET = 'Z18522'

# Short concept labels (generator prepends "GR<n> "; all stay < 50 chars).
LABELS = {
  1 => 'simple period boundary', 2 => 'question-mark boundary', 3 => 'exclamation boundary',
  4 => 'uppercase middle initial', 5 => 'lowercase abbrev (p.)', 6 => 'co. mid-sentence',
  7 => 'Inc. mid-sentence', 8 => 'co. at sentence end', 9 => 'Inc. at sentence end',
  10 => 'prepositive abbrev (Mt.)', 11 => 'prepositive + postpositive', 12 => "possessive abbrev (Jr.'s)",
  13 => 'acronym mid-sentence (U.S.A.)', 14 => 'acronym at sentence end (E.U.)', 15 => 'U.S. as boundary',
  16 => 'U.S. + capitalized word', 17 => 'U.S. + lowercase word', 18 => 'a.m./p.m. + honorific (Holy Grail)',
  19 => 'decimal/money non-boundary', 20 => 'decimal/money then boundary', 21 => 'parenthetical non-boundary',
  22 => 'email then boundary', 23 => 'web address then boundary', 24 => 'single quotes non-boundary',
  25 => 'double quotes non-boundary', 26 => 'double quotes close sentence', 27 => 'double exclamation',
  28 => 'double question', 29 => 'exclamation + question', 30 => 'question + exclamation',
  31 => 'list: N.) no trailing period', 32 => 'list: N.) with period', 33 => 'list: N) no trailing period',
  34 => 'list: N) with period', 35 => 'list: N. no trailing period', 36 => 'list: N. with period',
  37 => 'list: bullet', 38 => 'list: hyphen-bullet', 39 => 'list: alphabetical',
  40 => 'errant newline kept', 41 => 'errant newline collapses', 42 => 'newline-separated items',
  43 => 'numeric id with periods', 44 => "named entity with '!'", 45 => "pronoun 'I.' vs middle initial",
  46 => 'spaced ellipsis in quotation', 47 => 'bracketed ellipsis + citation', 48 => 'spaced ellipsis then boundary',
  49 => 'run-together ellipsis (4 dots)', 50 => 'mid-thought ellipses', 51 => 'four-dot ellipsis continuation',
  52 => 'no whitespace between sentences'
}.freeze

def rules
  JSON.parse(File.read(DATA))['rules']
end

def label_for(n)
  short = LABELS[n] or raise "no label for rule #{n}"
  label = "GR#{n} #{short}"
  raise "label too long (#{label.length}): #{label}" if label.length > 50

  label
end

def tester_z2(rule)
  n = rule['n']
  test_call = {
    'Z1K1' => 'Z7', 'Z7K1' => TARGET,
    "#{TARGET}K1" => { 'Z1K1' => 'Z6', 'Z6K1' => rule['input'] }
  }
  # Z889K1 (first list) is intentionally omitted: the tester framework
  # injects the function result there. K2 = expected list, K3 = Z866.
  validator = {
    'Z1K1' => 'Z7', 'Z7K1' => 'Z889',
    'Z889K2' => ['Z6'] + rule['expected'],
    'Z889K3' => 'Z866'
  }
  content = { 'Z1K1' => 'Z20', 'Z20K1' => TARGET, 'Z20K2' => test_call, 'Z20K3' => validator }
  WfZObjectEmitter.new_persistent(content, label: label_for(n))
end

def summary_for(rule)
  "Golden Rule #{rule['n']}: #{rule['concept']}"
end

mode = ARGV[0]
case mode
when '--list'
  rules.each { |r| puts format('%2d  %-50s  -> %d sentence(s)', r['n'], label_for(r['n']), r['expected'].length) }
when '--rule'
  n = ARGV[1].to_i
  rule = rules.find { |r| r['n'] == n } or abort "no rule #{n}"
  puts JSON.pretty_generate(tester_z2(rule))
when '--validate'
  ok = 0
  rules.each do |r|
    z2 = tester_z2(r)
    c = z2['Z2K2']
    raise "rule #{r['n']}: bad Z20" unless c['Z1K1'] == 'Z20' && c['Z20K2'] && c['Z20K3']
    raise "rule #{r['n']}: expected list mismatch" unless c.dig('Z20K3', 'Z889K2') == ['Z6'] + r['expected']

    ok += 1
  end
  puts "validated #{ok}/#{rules.length} testers build cleanly"
else
  warn 'usage: gen_segmentation_testers.rb --list | --rule N | --validate'
  exit 1
end
