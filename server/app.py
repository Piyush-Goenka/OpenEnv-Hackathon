import os
import uvicorn
from openenv.core.env_server import create_fastapi_app

from server.environment import DevReliabilityEnvironment
from models import DevReliabilityAction, DevReliabilityObservation

app = create_fastapi_app(
    DevReliabilityEnvironment,
    action_cls=DevReliabilityAction,
    observation_cls=DevReliabilityObservation
)

def main():
    port = int(os.environ.get("PORT", 7860))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("server.app:app", host=host, port=port)

if __name__ == "__main__":
    main()
