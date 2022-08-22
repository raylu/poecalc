#!/usr/bin/env python3

import sys
if len(sys.argv) == 3:
	import eventlet
	import eventlet.wsgi
	eventlet.monkey_patch()

# pylint: disable=wrong-import-position
import mimetypes

from pigwig import PigWig, Response
from pigwig.exceptions import HTTPException

import auras

def root(request):
	return Response.render(request, 'index.jinja2', {})

def analyze_auras(request, account, character):
	results = '\n\n'.join('\n'.join(ar) for ar in aura_analyzer.analyze(account, character))
	return Response.render(request, 'auras.jinja2',
			{'results': results, 'account': account, 'character': character})

def static(request, path):
	content_type, _ = mimetypes.guess_type(path)
	try:
		with open('static/' + path, 'rb') as f:
			return Response(f.read(), content_type=content_type)
	except FileNotFoundError:
		raise HTTPException(404, '%r not found\n' % path) # pylint: disable=raise-missing-from

routes = [
	('GET', '/', root),
	('GET', '/auras/<account>/<character>', analyze_auras),
	('GET', '/static/<path:path>', static),
]

app = PigWig(routes, template_dir='templates')
aura_analyzer = auras.Auras()

def main():
	if len(sys.argv) == 3:
		addr = sys.argv[1]
		port = int(sys.argv[2])
		eventlet.wsgi.server(eventlet.listen((addr, port)), app)
	else:
		app.main()

if __name__ == '__main__':
	main()
