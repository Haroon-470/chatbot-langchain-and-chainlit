from langchain_ollama import ChatOllama
import chainlit as cl
import asyncio
llm=ChatOllama(model="qwen2.5:0.5b")

@cl.on_chat_start
async def on_chat_start():
    #app_user=cl.user_session.get("user")
    await cl.Message(content=f"Hi Sir! How can i asist you toaday.").send()

@cl.on_message
async def on_message(message: cl.Message):
    print("The user sent: ", message.content)
    
    #If yoou want direct respobse 
    #You should have follow this code 

    #response= await llm.ainvoke(msg.content)
    #await cl.Message(response.content).send()

    #For streaming purpose the code below will be used
    # Create empty message to stream tokens into
    msg = cl.Message(content="")
    async for chunk in llm.astream(message.content):
        if chunk and hasattr(chunk, "content"):
            await msg.stream_token(chunk.content)
    #await cl.Message(msg).send()
    await msg.send()
    print("This the value of the llm response:\t",msg.content)
@cl.on_stop
async def on_stop():
    print("The user wants to stop the task!")

@cl.on_chat_end
async def on_chat_end():
    print("The user disconnected!")

# from chainlit.types import ThreadDict

# @cl.on_chat_resume
# async def on_chat_resume(thread: ThreadDict):
#     print("The user resumed a previous chat session!")

# response=llm.invoke("hi")
# print(response)