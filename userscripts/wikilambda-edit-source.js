/*
 * wikilambda-edit-source.js
 *
 * Adds "Edit Raw JSON" and "Create Raw JSON" links to the page-views
 * portlet on Wikifunctions. Each opens an inline editor backed by a
 * textarea and a summary field; Save posts through the
 * `wikilambda_edit` API action.
 *
 *   - Edit Raw JSON   — on any Z-page, fetches the stored JSON via
 *                       ?action=raw and saves with zid=<current>.
 *   - Create Raw JSON — on any Wikifunctions page, opens an empty
 *                       editor; Save omits the zid parameter, and on
 *                       success the page navigates to the new ZID.
 *
 * Stable element IDs (for automation / scripting):
 *     #wf-raw-json-widget     — the widget container
 *     #wf-raw-json-textarea   — the JSON textarea
 *     #wf-raw-json-summary    — the edit-summary input
 *     #wf-raw-json-save       — the Save button
 *     #wf-raw-json-close      — the Close button
 *     #wf-raw-json-status     — the inline status span
 *     #wf-raw-json-mode       — a data attribute on the widget: 'edit' | 'create'
 *     #pt-wf-raw-json-edit    — the portlet link for Edit Raw JSON
 *     #pt-wf-raw-json-create  — the portlet link for Create Raw JSON
 *
 * This is a fork, maintained in the wikifunctioneering repository
 * (https://github.com/ragesoss/wikifunctioneering), of:
 *   - User:Feeglgeef/wikilambda_editsource.js  (upstream; direct parent)
 *   - User:מקף/wikilambda_editsource.js         (original)
 *
 * Install
 * -------
 * 1. Copy the contents of this file to a user-JS page on Wikifunctions,
 *    e.g. [[User:YourName/wikilambda_editsource.js]].
 * 2. Add a loader line to [[Special:MyPage/common.js]]:
 *
 *      mw.loader.load( '//www.wikifunctions.org/w/index.php?title=User:YourName/wikilambda_editsource.js&action=raw&ctype=text/javascript' );
 *
 * 3. Reload any Wikifunctions page. "Create Raw JSON" appears in the
 *    page-views portlet; on Z-pages, "Edit Raw JSON" appears too.
 */

( function () {
	'use strict';

	const EDIT_LABEL = 'Edit Raw JSON';
	const EDIT_TOOLTIP = 'Edit this ZObject as raw JSON';
	const EDIT_DEFAULT_SUMMARY = 'edit via raw-JSON portlet';

	const CREATE_LABEL = 'Create Raw JSON';
	const CREATE_TOOLTIP = 'Create a new ZObject from raw JSON';
	const CREATE_DEFAULT_SUMMARY = 'create via raw-JSON portlet';

	const WIDGET_ID = 'wf-raw-json-widget';

	const zid = window.location.href.match( /\/(Z\d+)\b/ )?.[ 1 ];

	function fetchJson( z ) {
		const url = mw.util.getUrl( z, { action: 'raw' } );
		return fetch( url ).then( function ( r ) {
			if ( !r.ok ) {
				throw new Error( 'HTTP ' + r.status + ' fetching ' + z );
			}
			return r.text();
		} );
	}

	// POST to wikilambda_edit. `targetZid` null/undefined for creates
	// (the server treats an absent zid as "assign a new one"; Z2K1 in
	// the zobject is expected to be a Z0 placeholder in that case).
	function save( targetZid, newJson, summary ) {
		const api = new mw.Api();
		const params = {
			action: 'wikilambda_edit',
			format: 'json',
			assert: 'user',
			summary: summary,
			zobject: newJson,
			token: mw.user.tokens.get( 'csrfToken' )
		};
		if ( targetZid ) {
			params.zid = targetZid;
		}
		return api.post( params );
	}

	function describeError( code, data ) {
		// mw.Api rejects its Deferred as (code, data). `code` is a short
		// string like 'http' or 'ratelimited'; `data` usually carries the
		// detailed API error object. Either may be missing.
		if ( data && data.error && data.error.info ) {
			return ( data.error.code || code ) + ': ' + data.error.info;
		}
		if ( data && data.exception ) {
			return code + ': ' + data.exception;
		}
		if ( typeof code === 'string' ) {
			return code;
		}
		try {
			return JSON.stringify( code );
		} catch ( _ ) {
			return String( code );
		}
	}

	function openEditor( options ) {
		const mode = options.mode;
		const targetZid = options.zid || null;
		const initialContent = options.content || '';
		const defaultSummary = mode === 'create' ? CREATE_DEFAULT_SUMMARY : EDIT_DEFAULT_SUMMARY;

		const editor = $(
			'<div class="ext-wikilambda-widget-base" ' +
			'id="' + WIDGET_ID + '" ' +
			'data-wf-mode="' + mode + '" ' +
			'style="background-color: ghostwhite; max-width: none; padding: 0.5em;"></div>'
		);

		const textarea = $( '<textarea id="wf-raw-json-textarea"></textarea>' )
			.css( {
				width: '100%',
				height: '350px',
				'min-height': '200px',
				resize: 'vertical',
				direction: 'ltr',
				'font-family': 'monospace'
			} )
			.val( initialContent );

		const summaryInput = $( '<input id="wf-raw-json-summary">' )
			.attr( {
				type: 'text',
				placeholder: 'Summary (default: "' + defaultSummary + '")'
			} )
			.css( {
				width: '75%',
				height: '30px',
				'margin-top': '0.25em'
			} );

		const status = $( '<span id="wf-raw-json-status"></span>' )
			.css( { 'margin-right': '0.5em', color: '#555' } );

		const saveBtn = $( '<button id="wf-raw-json-save">Save</button>' )
			.addClass(
				'cdx-button cdx-button--action-progressive ' +
				'cdx-button--weight-primary cdx-button--size-medium cdx-button--framed'
			)
			.css( { float: 'inline-end', margin: '0 0 0 0.25em' } );

		const closeBtn = $( '<button id="wf-raw-json-close">Close</button>' )
			.addClass(
				'cdx-button cdx-button--action-default ' +
				'cdx-button--weight-primary cdx-button--size-medium cdx-button--framed'
			)
			.css( { float: 'inline-end', margin: '0' } );

		saveBtn.on( 'click', function () {
			const value = textarea.val();
			if ( !value ) {
				mw.notify( 'Please fill the source', { type: 'warn' } );
				return;
			}
			// "No changes" guard only meaningful in edit mode: in create
			// mode the textarea starts empty (or with a template) and any
			// non-empty content is a real candidate.
			if ( mode === 'edit' && value === initialContent ) {
				mw.notify( 'No changes detected', { type: 'warn' } );
				return;
			}
			try {
				JSON.parse( value );
			} catch ( e ) {
				mw.notify( 'Invalid JSON: ' + e.message, {
					type: 'error',
					autoHide: false
				} );
				return;
			}

			saveBtn.prop( 'disabled', true );
			closeBtn.prop( 'disabled', true );
			status.text( 'Saving…' );

			const summary = summaryInput.val() || defaultSummary;

			save( targetZid, value, summary ).then(
				function ( response ) {
					editor.remove();
					const newZid = response &&
						response.wikilambda_edit &&
						response.wikilambda_edit.page;
					if ( mode === 'create' && newZid ) {
						// Navigate to the freshly-created page so the
						// user lands on it.
						window.location.assign( mw.util.getUrl( newZid ) );
					} else {
						mw.notify(
							$( '<a>' )
								.append( $( '<strong>' ).text( 'Saved — click to reload' ) )
								.on( 'click', function () {
									window.location.assign(
										window.location.href.replace(
											/#wf-raw-json-.*$/, ''
										)
									);
								} ),
							{ autoHide: false }
						);
					}
				},
				function ( code, data ) {
					saveBtn.prop( 'disabled', false );
					closeBtn.prop( 'disabled', false );
					status.text( '' );
					// Log the raw failure so it's inspectable via devtools.
					mw.log.error( 'wikilambda_edit failed', code, data );
					mw.notify(
						$( '<strong>' ).text( 'Save failed: ' + describeError( code, data ) ),
						{ type: 'error', autoHide: false }
					);
				}
			);
		} );

		closeBtn.on( 'click', function () {
			editor.remove();
		} );

		const buttonBar = $( '<div></div>' )
			.css( { 'margin-top': '0.5em', overflow: 'auto' } )
			.append( saveBtn, closeBtn, status );

		editor.append( textarea, summaryInput, buttonBar );
		$( '#bodyContent' ).prepend( editor );
	}

	function openForEdit() {
		$( '#' + WIDGET_ID ).remove();
		if ( !zid ) {
			return;
		}
		fetchJson( zid ).then(
			function ( body ) {
				openEditor( { mode: 'edit', zid: zid, content: body } );
			},
			function ( err ) {
				mw.notify(
					$( '<strong>' ).text( 'Fetch failed: ' + ( err && err.message ? err.message : err ) ),
					{ type: 'error', autoHide: false }
				);
			}
		);
	}

	function openForCreate() {
		$( '#' + WIDGET_ID ).remove();
		openEditor( { mode: 'create', zid: null, content: '' } );
	}

	$.when(
		mw.loader.using( [ 'mediawiki.util', 'mediawiki.api' ], $.ready )
	).then( function () {
		const contentModel = mw.config.get( 'wgPageContentModel' );
		const editEligible =
			contentModel === 'wikilambda' ||
			contentModel === 'Wikibase Item' ||
			!!zid;

		if ( editEligible ) {
			const editNode = mw.util.addPortletLink(
				'p-views',
				'#wf-raw-json-edit',
				EDIT_LABEL,
				'pt-wf-raw-json-edit',
				EDIT_TOOLTIP,
				'r'
			);
			$( editNode ).on( 'click', function ( e ) {
				e.preventDefault();
				openForEdit();
			} );
		}

		// Create mode is available everywhere on Wikifunctions: you
		// never need an existing target to start a new ZObject.
		const createNode = mw.util.addPortletLink(
			'p-views',
			'#wf-raw-json-create',
			CREATE_LABEL,
			'pt-wf-raw-json-create',
			CREATE_TOOLTIP,
			'n'
		);
		$( createNode ).on( 'click', function ( e ) {
			e.preventDefault();
			openForCreate();
		} );
	} );
}() );
