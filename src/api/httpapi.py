import asyncio

from aiohttp import web

app = web.Application()

async def index(request):
    return web.Response(text='index')

# send the JS frontend client
# TODO: send a js file
async def capture_ui(request):
    return web.Response(text='capture_ui')

# update capture config
# TODO: API specifications for this
async def config_update(request):
    return web.Response(text="config_update")

# method to add routes from other modules
# TODO: support more than just get
def add_http_route(endpoint, callback):
    app.router.add_routes([web.get(endpoint, callback)])

# start the webserver
def init_app(port):
    # connect endpoints here
    app.router.add_routes([web.get('/', index),
                           web.get('/cap_ui', capture_ui),
                           web.post('/cfg_update', config_update)])
    
    web.run_app(app, port=port)
