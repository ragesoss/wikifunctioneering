#!/usr/bin/env ruby
# frozen_string_literal: true

# Probe the `wikilambda_edit` API via a Selenium-controlled Chrome session.
#
# Confirms that (a) the in-browser fetch path works identically to the
# userscript portlet and (b) a no-op round-trip through the API succeeds
# from inside a real logged-in session. Prints the response Ruby-side so
# we can see exactly what the API returns (and how errors surface).
#
# Usage:
#   ruby scripts/wf_api_probe.rb ZID [--summary TEXT] [--browser chrome|firefox]

require 'json'
require 'optparse'
require_relative 'wf_browser'

options = {
  browser: :chrome,
  summary: 'wf_api_probe round-trip (no change)'
}

OptionParser.new do |opts|
  opts.banner = "Usage: #{$PROGRAM_NAME} ZID [options]"
  opts.on('--summary TEXT', 'Edit summary') { |s| options[:summary] = s }
  opts.on('--browser NAME', 'firefox or chrome (default: chrome)') do |b|
    options[:browser] = b.to_sym
  end
end.parse!

zid = ARGV.shift
unless zid && zid.match?(/\AZ\d+\z/)
  warn "Usage: #{$PROGRAM_NAME} ZID [--summary TEXT] [--browser NAME]"
  exit 1
end

# The JS we inject. Structure mirrors the userscript but returns
# everything to Ruby instead of rendering UI. Uses the jQuery-Deferred
# (code, data) callback pair rather than await, because awaiting an
# mw.Api rejection collapses the data arg.
PROBE_JS = <<~JS
  const zid = arguments[0];
  const summary = arguments[1];
  const callback = arguments[arguments.length - 1];

  (async () => {
    try {
      const rawUrl = mw.util.getUrl(zid, { action: 'raw' });
      const rawResponse = await fetch(rawUrl);
      if (!rawResponse.ok) {
        callback({ ok: false, stage: 'fetch', status: rawResponse.status });
        return;
      }
      const body = await rawResponse.text();

      const api = new mw.Api();
      api.post({
        action: 'wikilambda_edit',
        format: 'json',
        assert: 'user',
        summary: summary,
        zid: zid,
        zobject: body,
        token: mw.user.tokens.get('csrfToken')
      }).then(
        function (response) {
          callback({
            ok: true,
            bodyLength: body.length,
            bodyPreview: body.slice(0, 200),
            bodyTail: body.slice(-120),
            response: response
          });
        },
        function (code, data) {
          let dataSnapshot;
          try {
            // JSON round-trip strips any non-serialisable bits (jqXHR
            // objects etc.) so Selenium can return the payload to Ruby.
            dataSnapshot = JSON.parse(JSON.stringify(data));
          } catch (_) {
            dataSnapshot = String(data);
          }
          callback({
            ok: false,
            stage: 'post',
            bodyLength: body.length,
            bodyPreview: body.slice(0, 200),
            error: { code: code, data: dataSnapshot }
          });
        }
      );
    } catch (e) {
      callback({ ok: false, stage: 'throw', error: String(e) });
    }
  })();
JS

wf = WfBrowser.new(browser: options[:browser])

begin
  wf.launch
  wf.ensure_logged_in

  wf.navigate_to("#{WfBrowser::WF_BASE}/wiki/#{zid}")
  wf.log "Probing round-trip for #{zid}..."

  # The fetch + POST together can take several seconds; default script
  # timeout is too short.
  wf.driver.manage.timeouts.script_timeout = 30

  result = wf.driver.execute_async_script(PROBE_JS, zid, options[:summary])

  puts ''
  puts '─── Probe result ───────────────────────────────────────'
  puts JSON.pretty_generate(result)
  puts '────────────────────────────────────────────────────────'

  wf.quit
  exit(result['ok'] ? 0 : 2)
rescue StandardError => e
  puts "\nERROR: #{e.message}"
  e.backtrace.first(5).each { |line| puts "  #{line}" }
  begin
    wf.save_debug_screenshot('api-probe-error')
  rescue StandardError
    # best effort
  end
  wf.quit
  exit 1
end
