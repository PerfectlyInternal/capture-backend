import asyncio

from aiohttp import web

# send the JS frontend client
# TODO: send a js file
async def capture_ui(request):
    return web.Response(text='capture_ui')

# update capture config
# TODO: API specifications for this
async def config_update(request):
    return web.Response(text="config_update")

# start the webserver
def init_app(port):
    app = web.Application()

    # connect endpoints here
    app.add_routes([web.get('/capture_ui' capture_ui)])
    app.add_routes([web.get('/config_update' config_update)])
    
    web.run_app(app)
