from openenv.core.env_server import create_fastapi_app

from server.environment import DevReliabilityEnvironment

app = create_fastapi_app(DevReliabilityEnvironment)
