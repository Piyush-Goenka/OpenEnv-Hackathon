from openenv.core.env_server import create_fastapi_app

from server.environment import HackathonEnvironment

app = create_fastapi_app(HackathonEnvironment)
