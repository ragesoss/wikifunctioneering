#!/usr/bin/env ruby
# frozen_string_literal: true

# Diagnostic: dumps the DOM structure of the function creation page.

$stdout.sync = true

require 'fileutils'
require 'selenium-webdriver'

PROFILE_DIR = File.expand_path('../../.browser-profile', __FILE__)
WF_BASE = 'https://www.wikifunctions.org'

puts 'Launching chrome...'
options = Selenium::WebDriver::Chrome::Options.new
options.add_argument("--user-data-dir=#{PROFILE_DIR}")
driver = Selenium::WebDriver.for(:chrome, options: options)
driver.manage.window.resize_to(1400, 900)
wait = Selenium::WebDriver::Wait.new(timeout: 30)

url = "#{WF_BASE}/w/index.php?title=Special:CreateObject&uselang=en&zid=Z8"
puts "Opening #{url}..."
driver.navigate.to(url)
wait.until { driver.find_element(css: '[data-testid="publish-button"]') rescue nil }
puts 'Page ready.'
sleep 2

# Dump all data-testid elements
puts ''
puts '=== Elements with data-testid ==='
elements = driver.find_elements(css: '[data-testid]')
elements.each do |el|
  testid = el.attribute('data-testid')
  tag = el.tag_name
  classes = el.attribute('class')&.split&.first(3)&.join(' ')
  displayed = el.displayed? rescue false
  next unless displayed

  puts "  #{testid} (#{tag}, #{classes})"
end

# Dump all visible inputs
puts ''
puts '=== Visible inputs ==='
inputs = driver.find_elements(css: 'input, select, textarea')
inputs.select { |i| i.displayed? rescue false }.each do |input|
  type = input.attribute('type')
  placeholder = input.attribute('placeholder')
  id = input.attribute('id')
  classes = input.attribute('class')&.split&.first(3)&.join(' ')
  parent_testid = driver.execute_script(<<~JS, input)
    let el = arguments[0];
    while (el) {
      if (el.dataset && el.dataset.testid) return el.dataset.testid;
      el = el.parentElement;
    }
    return null;
  JS
  puts "  #{type || 'text'} | placeholder=#{placeholder.inspect} | id=#{id.inspect} | parent-testid=#{parent_testid.inspect} | class=#{classes}"
end

# Dump all visible lookup inputs
puts ''
puts '=== Visible ZObjectSelector lookups ==='
lookups = driver.find_elements(css: '.cdx-text-input__input')
lookups.select { |l| l.displayed? rescue false }.each do |lookup|
  placeholder = lookup.attribute('placeholder')
  parent_testid = driver.execute_script(<<~JS, lookup)
    let el = arguments[0];
    while (el) {
      if (el.dataset && el.dataset.testid) return el.dataset.testid;
      el = el.parentElement;
    }
    return null;
  JS
  parent_id = driver.execute_script(<<~JS, lookup)
    let el = arguments[0];
    while (el) {
      if (el.id) return el.id;
      el = el.parentElement;
    }
    return null;
  JS
  puts "  placeholder=#{placeholder.inspect} | parent-testid=#{parent_testid.inspect} | parent-id=#{parent_id.inspect}"
end

puts ''
puts 'Done. Press Ctrl+C to quit.'
begin
  sleep
rescue Interrupt
  puts 'Bye.'
end
