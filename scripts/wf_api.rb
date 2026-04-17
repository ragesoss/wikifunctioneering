# frozen_string_literal: true

# API primitives for the `wikilambda_edit` endpoint, executed inside the
# Selenium-controlled browser's session.
#
# Why run through the browser rather than a standalone HTTP client:
# wikilambda-* rights are not registered in $wgGrantPermissions, so
# bot-password and OAuth-scoped tokens get Z557 back. A full user
# session (the one our persistent Chrome profile already carries) does
# have those rights, and executing `fetch` / `mw.Api` inside that
# session piggybacks on them cleanly.
#
# Mixed into WfBrowser so callers can say `wf.api_fetch_raw(zid)` and
# `wf.api_wikilambda_edit(zid: ..., zobject: ..., summary: ...)`.

module WfApi
  # GET /wiki/<zid>?action=raw, returning the canonical-form JSON body.
  FETCH_JS = <<~JS
    const zid = arguments[0];
    const callback = arguments[arguments.length - 1];
    (async () => {
      try {
        const url = mw.util.getUrl(zid, { action: 'raw' });
        const response = await fetch(url);
        if (!response.ok) {
          callback({ ok: false, stage: 'fetch', status: response.status });
          return;
        }
        const body = await response.text();
        callback({ ok: true, body: body });
      } catch (e) {
        callback({ ok: false, stage: 'fetch', error: String(e) });
      }
    })();
  JS

  # POST to api.php action=wikilambda_edit via mw.Api (uses the session
  # CSRF token). Uses .then(success, failure) rather than await because
  # awaiting an mw.Api rejection collapses the (code, data) pair into
  # just the first value.
  POST_JS = <<~JS
    const zid = arguments[0];
    const zobject = arguments[1];
    const summary = arguments[2];
    const callback = arguments[arguments.length - 1];
    const api = new mw.Api();
    api.post({
      action: 'wikilambda_edit',
      format: 'json',
      assert: 'user',
      summary: summary,
      zid: zid,
      zobject: zobject,
      token: mw.user.tokens.get('csrfToken')
    }).then(
      function (response) {
        callback({ ok: true, response: response });
      },
      function (code, data) {
        let dataSnapshot;
        try {
          // Strip jqXHR-style non-serialisable fields so the payload
          // survives Selenium's return trip.
          dataSnapshot = JSON.parse(JSON.stringify(data));
        } catch (_) {
          dataSnapshot = String(data);
        }
        callback({ ok: false, stage: 'post', code: code, data: dataSnapshot });
      }
    );
  JS

  FETCH_TIMEOUT = 30
  POST_TIMEOUT = 60

  # Return the raw canonical JSON string for a persistent Z-object.
  def api_fetch_raw(zid)
    ensure_session_ready
    @driver.manage.timeouts.script_timeout = FETCH_TIMEOUT
    result = @driver.execute_async_script(FETCH_JS, zid)
    return result['body'] if result['ok']

    detail = result['status'] ? "HTTP #{result['status']}" : result['error']
    raise "api_fetch_raw(#{zid}) failed: #{detail}"
  end

  # POST a canonical-form ZObject JSON string via wikilambda_edit.
  # Returns the inner `wikilambda_edit` response hash on success, e.g.
  # { "articleId" => 80476, "page" => "Z33682", "success" => "",
  #   "title" => "Z33682" }. Raises on API error with code + info.
  def api_wikilambda_edit(zid:, zobject:, summary:)
    ensure_session_ready
    @driver.manage.timeouts.script_timeout = POST_TIMEOUT
    result = @driver.execute_async_script(POST_JS, zid, zobject, summary)
    if result['ok']
      result.dig('response', 'wikilambda_edit') || result['response']
    else
      info = result.dig('data', 'error', 'info') || result['code']
      code = result['code']
      raise "wikilambda_edit(#{zid}) failed: #{code}: #{info}"
    end
  end

  private

  # mw.Api + mw.util need to be loaded. Every Wikifunctions page loads
  # them, so this is just a guard against being called before the first
  # navigation.
  def ensure_session_ready
    wait_for_mw_config
    ready = @driver.execute_script(
      'return typeof mw !== "undefined" && !!mw.Api && !!mw.util'
    )
    return if ready

    raise 'wf_api: mw.Api not available — navigate to a Wikifunctions page first'
  end
end
