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

def analyze_auras(request, account, character, aura_effect=None):
	# eventlet encodes PATH_INFO as latin1
	# https://github.com/eventlet/eventlet/blob/890f320b/eventlet/wsgi.py#L690
	# because PEP-0333 says so https://github.com/eventlet/eventlet/pull/497
	account = account.encode('latin1').decode('utf-8')
	character = character.encode('latin1').decode('utf-8')
	if aura_effect:
		aura_effect = int(aura_effect.encode('latin1').decode('utf-8'))
	results, vaal_results = aura_analyzer.analyze(account, character, aura_effect)
	result_str = '\n\n'.join('\n'.join(ar) for ar in results)
	vaal_result_str = '\n\n'.join('\n'.join(ar) for ar in vaal_results)
	return Response.render(request, 'auras.jinja2', {
		'results': result_str,
		'vaal_results': vaal_result_str,
		'account': account,
		'character': character,
	})

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
	('GET', '/auras/<account>/<character>/<aura_effect>', analyze_auras),
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
