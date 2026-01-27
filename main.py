from fastapi import FastAPI
from chainlit.utils import mount_chainlit

app = FastAPI()


@app.get("/")
def read_main():
    return {"message": "Hello World from main app"}

# mount_chainlit(app=app, target="sql_agent.py", path="/chainlit")
mount_chainlit(app=app, target="streaming.py", path="/")