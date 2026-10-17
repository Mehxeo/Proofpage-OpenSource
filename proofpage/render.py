"""Optional isolated JS rendering with all outbound requests mediated by the safe fetcher."""
import time
import urllib.parse


def render_html(url, body, allowed):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ValueError('Rendering is not installed. Install proofpage[render] and run python -m playwright install chromium.') from None

    deadline, requests, blocked = time.monotonic()+30, 0, 0
    host = urllib.parse.urlsplit(url).hostname
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception:
            raise ValueError('Chromium is unavailable. Run python -m playwright install chromium.') from None
        try:
            context = browser.new_context(service_workers='block', accept_downloads=False)
            context.route_web_socket('**/*', lambda socket: socket.close())
            def route_request(route):
                nonlocal requests, blocked
                request = route.request
                requests += 1
                if requests > 20 or time.monotonic() > deadline or request.method != 'GET' or request.resource_type not in ('document', 'script', 'xhr', 'fetch', 'stylesheet'):
                    blocked += 1
                    return route.abort()
                target = request.url
                if urllib.parse.urlsplit(target).hostname != host or not allowed(target):
                    blocked += 1
                    return route.abort()
                try:
                    if target.rstrip('/') == url.rstrip('/') and request.resource_type == 'document':
                        route.fulfill(status=200, content_type='text/html', body=body)
                    else:
                        blocked += 1
                        route.abort()
                except Exception:
                    blocked += 1
                    route.abort()
            context.route('**/*', route_request)
            page = context.new_page()
            page.goto(url, wait_until='networkidle', timeout=30000)
            rendered = page.content()
            if len(rendered.encode()) > 8*1024*1024:
                raise ValueError('Rendered page exceeds the 8 MiB limit.')
            return rendered, {'rendered': True, 'requests': requests, 'blocked_requests': blocked,
                              'coverage': 'Offline render of captured HTML and inline JavaScript. External scripts and network calls are blocked; dynamic content depending on them is not captured.'}
        finally:
            browser.close()
