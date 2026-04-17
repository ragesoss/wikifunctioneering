#!/usr/bin/env ruby
# frozen_string_literal: true

# Diagnostic: reproduces the nested-lookup failure state (Z21806K1 in
# function-call mode, with a type-auto-picked function populating Z7K1),
# then dumps everything about that Z7K1 slot so we know how to clear it.

$stdout.sync = true

require_relative 'wf_browser'

wf = WfBrowser.new(browser: :chrome)
wf.launch
wf.ensure_logged_in

# Open Z33668 and click Add implementation
wf.navigate_to("#{WfBrowser::WF_BASE}/view/en/Z33668")
wait = Selenium::WebDriver::Wait.new(timeout: 30)
wait.until { wf.safe_find('[data-testid="function-implementations-table"]') }
sleep 1

puts '-> Clicking Add implementation'
add_link = wf.driver.find_element(
  css: '[data-testid="function-implementations-table"] [data-testid="add-link"]'
)
add_link.click
wait.until { wf.safe_find('[data-testid="implementation-radio"]') }
sleep 1

# Ensure Composition mode
puts '-> Selecting Composition mode'
comp_radio = wf.driver.find_element(css: '[data-testid="implementation-radio"] input[value="Z14K2"]')
wf.driver.execute_script('arguments[0].click()', comp_radio) unless comp_radio.selected?
sleep 1

# Expand the composition root
puts '-> Expanding root'
2.times do
  z7k1 = wf.driver.find_elements(css: '[id*="Z14K2"][id*="Z7K1"]')
                   .find { |el| el.attribute('class')&.include?('object-key-value') }
  break if z7k1

  wf.click_first(wf.driver.find_element(css: '[data-testid="implementation-content"]'),
                  '[data-testid="object-to-string-link"]',
                  '[data-testid="expanded-toggle"]')
  sleep 1
end

z7k1 = wait.until do
  wf.driver.find_elements(css: '[id*="Z14K2"][id*="Z7K1"]')
            .find { |el| el.attribute('class')&.include?('object-key-value') }
end
prefix = z7k1.attribute('id').sub(/-Z7K1$/, '')
puts "Root prefix: #{prefix}"

# Select Z21806 at the root using the OLD logic (we know this works here)
puts '-> Selecting Z21806 at root'
root_container = wf.driver.find_element(id: "#{prefix}-Z7K1")
root_input = root_container.find_element(css: 'input.cdx-text-input__input')
root_input.send_keys('Z21806')
sleep 2
root_input.send_keys(:arrow_down)
sleep 0.5
root_input.send_keys(:return)
sleep 2

# Wait for Z21806K1 to appear
puts '-> Waiting for Z21806K1'
wait.until { wf.safe_find("[id='#{prefix}-Z21806K1']") }
sleep 1

# Switch Z21806K1 to function-call mode — but do it step-by-step with diag.
k1_keypath = "#{prefix}-Z21806K1"
puts "-> Switching #{k1_keypath} to Function call mode (step by step)"

k1_el = wf.driver.find_element(id: k1_keypath)
btn = k1_el.find_element(css: '[data-testid="mode-selector-button"]')
puts "  Before: aria-expanded=#{btn.attribute('aria-expanded').inspect}"
wf.scroll_to(btn)
sleep 0.5

btn.click
sleep 0.8
puts "  After click: aria-expanded=#{btn.attribute('aria-expanded').inspect}"

# Enumerate visible menu items (any mode-selector menu)
visible_items = wf.driver.find_elements(css: '.cdx-menu-item').select do |i|
  (i.displayed? rescue false)
end
puts "  Visible .cdx-menu-item count: #{visible_items.size}"
visible_items.each do |i|
  t = i.attribute('type')
  text = i.text.strip[0, 40]
  puts "    type=#{t.inspect} text=#{text.inspect} displayed=true"
end

# Try clicking the Z7 item
target = visible_items.find { |i| i.attribute('type') == 'Z7' }
if target
  puts "  Z7 item: aria-selected=#{target.attribute('aria-selected').inspect} " \
       "class=#{target.attribute('class').to_s.split.first(3).join(' ')}"
  puts "  Clicking Z7 item..."
  target.click
  sleep 1
  puts "  After Z7 click: aria-expanded=#{btn.attribute('aria-expanded').inspect}"
else
  puts "  No visible Z7 item found!"
end
sleep 2

# Now try clicking expanded-toggle to see if Z7K1 is just collapsed
puts "-> Clicking expanded-toggle on Z21806K1"
toggle = k1_el.find_element(css: '[data-testid="expanded-toggle"]')
wf.scroll_to(toggle)
sleep 0.5
toggle.click
sleep 2

puts "  IDs after expand:"
wf.driver.find_elements(css: "[id^='main-Z2K2-Z14K2-Z21806K1']").each do |el|
  puts "    #{el.attribute('id')}"
end
sleep 1

# Now dump everything about the nested Z7K1 slot
nested_z7k1_id = "#{k1_keypath}-Z7K1"
puts ''
puts "=== State of #{nested_z7k1_id} after function-call mode switch ==="

begin
  slot = wf.driver.find_element(id: nested_z7k1_id)
rescue Selenium::WebDriver::Error::NoSuchElementError
  puts "  Not found at #{nested_z7k1_id}! Dumping related state."

  puts ''
  puts '  All IDs starting with main-Z2K2-Z14K2-Z21806K1:'
  wf.driver.find_elements(css: "[id^='main-Z2K2-Z14K2-Z21806K1']").each do |el|
    puts "    #{el.attribute('id')}"
  end

  puts ''
  puts '  Z21806K1 slot outerHTML (truncated to 4000 chars):'
  k1_el = wf.driver.find_element(id: k1_keypath)
  puts k1_el.attribute('outerHTML')[0, 4000]
  puts '---'

  puts ''
  puts '  Z21806K1 inputs/buttons (visible):'
  k1_el.find_elements(css: 'input').each do |inp|
    next unless (inp.displayed? rescue false)

    puts "    input value=#{inp.attribute('value').inspect} " \
         "placeholder=#{inp.attribute('placeholder').inspect}"
  end
  k1_el.find_elements(css: 'button').each do |btn|
    next unless (btn.displayed? rescue false)

    puts "    button text=#{btn.text.strip[0, 40].inspect} " \
         "aria-label=#{btn.attribute('aria-label').inspect} " \
         "testid=#{btn.attribute('data-testid').inspect}"
  end
  puts ''

  puts '  Done. Closing browser.'
  wf.driver.quit rescue nil
  exit
end

puts "outerHTML (truncated to 3000 chars):"
html = slot.attribute('outerHTML')
puts html[0, 3000]
puts '---'
puts ''

puts 'Inputs inside slot:'
slot.find_elements(css: 'input').each do |inp|
  puts "  type=#{inp.attribute('type').inspect} value=#{inp.attribute('value').inspect} " \
       "placeholder=#{inp.attribute('placeholder').inspect} displayed=#{inp.displayed? rescue false}"
end
puts ''

puts 'Buttons inside slot (look for chip-close, remove, etc.):'
slot.find_elements(css: 'button').each do |btn|
  next unless (btn.displayed? rescue false)

  puts "  text=#{btn.text.strip[0, 40].inspect} aria-label=#{btn.attribute('aria-label').inspect} " \
       "class=#{btn.attribute('class')&.split&.first(4)&.join(' ').inspect}"
end
puts ''

puts 'Elements with "chip" or "remove" in class:'
slot.find_elements(css: '[class*="chip"], [class*="remove"]').each do |el|
  next unless (el.displayed? rescue false)

  puts "  <#{el.tag_name}> class=#{el.attribute('class').inspect} text=#{el.text.strip[0, 40].inspect}"
end
puts ''

puts 'Text content of slot (for context):'
puts "  #{slot.text.strip[0, 200].inspect}"
puts ''

# Now actually select Z33071 in the nested lookup using our updated logic
puts '== Selecting Z33071 via updated select_in_lookup =='
wf.select_in_lookup(nested_z7k1_id, 'Z33071')
sleep 3

puts "-> IDs under Z21806K1 after Z33071 selection:"
wf.driver.find_elements(css: "[id^='main-Z2K2-Z14K2-Z21806K1']").each do |el|
  puts "    #{el.attribute('id')}"
end
sleep 1

# Drill into Z33071K1 (collapsed by default) and dump everything.
k1k1_keypath = "#{k1_keypath}-Z33071K1"
puts ''
puts "== Dumping #{k1k1_keypath} (should be Z33071K1, lexical category) =="
begin
  k1k1 = wf.driver.find_element(id: k1k1_keypath)
rescue Selenium::WebDriver::Error::NoSuchElementError
  puts "  NOT FOUND. Cannot proceed."
  wf.driver.quit rescue nil
  exit
end

puts 'outerHTML of Z33071K1 slot (truncated to 4000 chars):'
puts k1k1.attribute('outerHTML')[0, 4000]
puts '---'

puts ''
puts 'Z33071K1 visible inputs:'
k1k1.find_elements(css: 'input').each do |inp|
  next unless (inp.displayed? rescue false)

  puts "  type=#{inp.attribute('type').inspect} value=#{inp.attribute('value').inspect} " \
       "placeholder=#{inp.attribute('placeholder').inspect}"
end

puts ''
puts 'Z33071K1 visible buttons:'
k1k1.find_elements(css: 'button').each do |btn|
  next unless (btn.displayed? rescue false)

  puts "  testid=#{btn.attribute('data-testid').inspect} " \
       "aria-label=#{btn.attribute('aria-label').to_s[0, 60].inspect} " \
       "disabled=#{btn.attribute('disabled').inspect} " \
       "text=#{btn.text.strip[0, 40].inspect}"
end

puts ''
puts 'Z33071K1 expanded-toggle state:'
t = k1k1.find_elements(css: '[data-testid="expanded-toggle"]').first
if t
  icon = t.find_elements(css: '.ext-wikilambda-app-expanded-toggle__icon').first
  puts "  toggle found, disabled=#{t.attribute('disabled').inspect}"
  puts "  icon class=#{icon&.attribute('class').inspect}"
else
  puts "  no toggle found in Z33071K1"
end

# Try clicking mode selector and dump menu items
puts ''
puts '== Clicking mode selector button on Z33071K1 =='
mode_btn = k1k1.find_elements(css: '[data-testid="mode-selector-button"]').first
if mode_btn
  puts "  Before click: aria-expanded=#{mode_btn.attribute('aria-expanded').inspect}"
  wf.scroll_to(mode_btn)
  sleep 0.5
  mode_btn.click
  sleep 1
  puts "  After click: aria-expanded=#{mode_btn.attribute('aria-expanded').inspect}"

  visible_items = wf.driver.find_elements(css: '.cdx-menu-item').select { |i| i.displayed? rescue false }
  puts "  Visible menu items: #{visible_items.size}"
  visible_items.each do |i|
    puts "    type=#{i.attribute('type').inspect} text=#{i.text.strip[0, 50].inspect}"
  end
else
  puts "  NO mode-selector-button visible in Z33071K1!"
end

puts ''
puts 'Done. Closing browser.'
wf.driver.quit rescue nil
