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
#   --mode MODE      api / ui / auto (default: auto)
#                    auto picks api for edits (spec has
#                    implementation_zid or tester_zid) and ui otherwise.

require 'json'
require 'optparse'
require_relative 'wf_browser'
require_relative 'wf_task_composition'
require_relative 'wf_task_function'
require_relative 'wf_task_tester'

options = { delay: 0.25, browser: :chrome, mode: :auto }

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
  opts.on('--mode MODE', %i[api ui auto], 'api / ui / auto (default: auto)') do |m|
    options[:mode] = m
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
task_name ||= 'tester'      if spec['validator'] || spec['test_call']
task_name ||= 'function'    if spec['inputs']

unless task_name
  warn 'Cannot determine task from spec. Include "task", "composition", or "inputs".'
  exit 1
end

# Auto-pick mode from the spec. Function-shell creation still needs
# the UI flow (the userscript supports creates generically, but our
# function-shell task helper is UI-only). Everything else — edits and
# compositions/testers creates — rides the userscript route.
def pick_mode(spec, task_name)
  return :ui if task_name == 'function'

  :api
end

mode = options[:mode]
mode = pick_mode(spec, task_name) if mode == :auto

if mode == :api && task_name == 'function'
  warn 'API mode does not support function-shell creation yet. Use --mode=ui.'
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
         when 'tester'
           WfTaskTester.new(wf, spec)
         else
           raise "Unknown task: #{task_name}"
         end

  wf.log "Mode: #{mode}"
  new_zid = mode == :api ? task.run_api : task.run
  success = true

  if mode == :api
    puts ''
    if new_zid
      puts "Populated Edit Raw JSON for #{new_zid}."
    else
      puts 'Populated Create Raw JSON (the server will assign a new ZID on save).'
    end
    puts 'Review the textarea + summary in the browser, then click Save.'
    puts 'Press Enter here when you are done (this closes the browser).'
    $stdin.gets
  else
    puts ''
    puts "Done: #{new_zid}"
  end
  wf.quit
rescue StandardError => e
  puts "\nERROR: #{e.message}"
  e.backtrace.first(5).each { |line| puts "  #{line}" }
  # Capture a final screenshot for post-mortem, then quit. (We used to
  # leave the browser open waiting for Ctrl+C, which made the whole run
  # stall indefinitely after any failed step.)
  begin
    wf.save_debug_screenshot('final-error')
  rescue StandardError
    # best effort
  end
  wf.quit
  exit 1
end
