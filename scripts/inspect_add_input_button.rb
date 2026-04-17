#!/usr/bin/env ruby
# frozen_string_literal: true

# Diagnostic: dumps all visible buttons on the function creation page
# to find the right selector for the "Add input" button.

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
sleep 3

puts ''
puts '=== All visible buttons ==='
buttons = driver.find_elements(css: 'button')
buttons.select { |b| b.displayed? rescue false }.each do |btn|
  text = btn.text.strip[0, 80]
  testid = btn.attribute('data-testid')
  classes = btn.attribute('class')&.split&.first(4)&.join(' ')
  aria_label = btn.attribute('aria-label')
  parent_testid = driver.execute_script(<<~JS, btn)
    let el = arguments[0].parentElement;
    while (el) {
      if (el.dataset && el.dataset.testid) return el.dataset.testid;
      el = el.parentElement;
    }
    return null;
  JS
  puts "  text=#{text.inspect}"
  puts "    testid=#{testid.inspect} aria-label=#{aria_label.inspect}"
  puts "    parent-testid=#{parent_testid.inspect}"
  puts "    class=#{classes}"
  puts ''
end

puts '=== Elements under function-editor-inputs ==='
begin
  container = driver.find_element(css: '[data-testid="function-editor-inputs"]')
  children = container.find_elements(css: '*')
  children.select { |c| c.displayed? rescue false }.first(20).each do |c|
    tag = c.tag_name
    testid = c.attribute('data-testid')
    classes = c.attribute('class')&.split&.first(3)&.join(' ')
    text = c.text.to_s.strip[0, 40]
    puts "  #{tag} testid=#{testid.inspect} class=#{classes.inspect} text=#{text.inspect}"
  end
rescue StandardError => e
  puts "  ERROR: #{e.message}"
end

puts ''
puts 'Done. Closing browser.'
driver.quit rescue nil
