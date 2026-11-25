from contextlib import asynccontextmanager

from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

from app import db
from app.schema import get_context, schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.create_tables()
    yield
    await db.engine.dispose()


app = FastAPI(title="Сервис доставки еды", lifespan=lifespan)
app.include_router(
    GraphQLRouter(
        schema, context_getter=get_context, graphql_ide="graphiql"),
    prefix="/graphql",
)
