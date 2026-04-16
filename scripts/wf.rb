#!/usr/bin/env ruby
# frozen_string_literal: true

# Entry point for Wikifunctions browser automation.
#
# Usage:
#   ruby scripts/wf.rb SPEC_FILE [options]
#
# The task is inferred from the spec:
#   - "composition" key present  → composition create/edit
#   - "inputs" key present       → function shell creation
#   - explicit "task" key        → override auto-detection
#
# Options:
#   --delay N        Seconds between steps (default: 0.7)
#   --browser NAME   firefox or chrome (default: chrome)

require 'json'
require 'optparse'
require_relative 'wf_browser'
require_relative 'wf_task_composition'
require_relative 'wf_task_function'

options = { delay: 0.7, browser: :chrome }

OptionParser.new do |opts|
  opts.banner = "Usage: #{$PROGRAM_NAME} SPEC_FILE [options]"
  opts.separator ''
  opts.separator 'Automates Wikifunctions tasks in the browser.'
  opts.separator ''
  opts.on('--delay N', Float, "Seconds between steps (default: #{options[:delay]})") do |d|
    options[:delay] = d
  end
  opts.on('--browser NAME', "firefox or chrome (default: #{options[:browser]})") do |b|
    options[:browser] = b.to_sym
  end
end.parse!

file = ARGV.shift
unless file
  warn "Usage: #{$PROGRAM_NAME} SPEC_FILE [--delay N] [--browser NAME]"
  exit 1
end

spec = JSON.parse(File.read(file))

# Determine which task to run
task_name = spec['task']
task_name ||= 'composition' if spec['composition']
task_name ||= 'function' if spec['inputs']

unless task_name
  warn 'Cannot determine task from spec. Include "task", "composition", or "inputs".'
  exit 1
end

wf = WfBrowser.new(browser: options[:browser], delay: options[:delay])

success = false
begin
  wf.launch
  wf.ensure_logged_in

  task = case task_name
         when 'composition'
           WfTaskComposition.new(wf, spec)
         when 'function'
           WfTaskFunction.new(wf, spec)
         else
           raise "Unknown task: #{task_name}"
         end

  new_zid = task.run
  success = true
  puts ''
  puts "Done: #{new_zid}"
  wf.quit
rescue StandardError => e
  puts "\nERROR: #{e.message}"
  e.backtrace.first(5).each { |line| puts "  #{line}" }
  puts 'Browser left open for inspection.'
  begin
    sleep
  rescue Interrupt
    puts "\nQuitting."
    wf.quit
  end
end
