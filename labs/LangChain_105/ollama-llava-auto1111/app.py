import base64
import json
import streamlit as st
from graph import app, ollama_base_url, a_1111_base_url
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    FunctionMessage,
    BaseMessage
)
from pandas.io.common import BytesIO
from PIL import Image

# Set title for the page and the site
st.set_page_config(page_title="LangChain with Automatic 1111 API")
st.title("LangChain with Automatic 1111 API")

# session state for conversation history
if "messages" not in st.session_state:
    st.session_state["messages"] = [AIMessage(content="How can I help you?")]

# session state to track uploaded file
if "uploaded_file" not in st.session_state:
    st.session_state["uploaded_file"] = None

# session state to track uploaded or generated image
if "image" not in st.session_state:
    st.session_state["image"] = None

# render all the messages in the conversation history
# render images if present
# if parameters exist for generated images, render them as well
for msg in st.session_state.messages:
    if "image" not in msg.additional_kwargs:
        st.chat_message(msg.type).write(msg.content)
    else:
        st.chat_message(msg.type).image(
            msg.additional_kwargs["image"], width=512
        )
        if "params" in msg.additional_kwargs:
            with st.chat_message(msg.type).expander("Parameters"):
                st.code(msg.additional_kwargs["params"])

# LangGraph Agent State
state = {}

# Sidebar
with st.sidebar:
    st.text(f"Ollama\n{ollama_base_url}")
    st.text(f"Automatic 1111\n{a_1111_base_url}")

if uploaded_file := st.sidebar.file_uploader("Upload an image file",
                                             type=["jpg", "png"]):
    if st.session_state.uploaded_file != uploaded_file:
        st.session_state.uploaded_file = uploaded_file
        st.session_state.image = (
            base64
            .b64encode(uploaded_file.getvalue())
            .decode()
        )
        st.session_state.messages.append(
            HumanMessage(
                content=uploaded_file.name,
                additional_kwargs={
                    "image": uploaded_file,
                }
            )
        )
        st.chat_message("user").image(uploaded_file, width=512)

if prompt := st.chat_input():
    # get user prompt from chat input and add it to conversation history
    # as well as to agent state
    human_message = HumanMessage(content=prompt)
    state["messages"] = [human_message]
    st.session_state.messages.append(human_message)
    st.chat_message("human").write(prompt)

    # clear previous response
    response = ""

    # if an uploaded or generated image is available, add it to agent state
    if st.session_state.image is not None:
        image = st.session_state.image
        state["image"] = image

    # invoke agent with state and grab the last message
    response = app.invoke(state)
    messages = response["messages"]
    last_message = messages[-1]

    if isinstance(last_message, AIMessage):
        # if last message is an AI response, show it to the user
        st.chat_message("assistant").write(last_message.content)
        st.session_state.messages.append(last_message)
    else:
        if isinstance(last_message, FunctionMessage):
            if last_message.name == "image2txt":
                # if message is a function response with answer about an
                # image show it to the user
                last_message.content = str(last_message.content).strip('"')
                st.chat_message(last_message.name).write(last_message.content)
                st.session_state.messages.append(last_message)
            elif last_message.name == "txt2image":
                # if message is a function response from image generation
                # show image to user along with it parameters
                # add image to the session state
                content = json.loads(str(last_message.content))
                imageb64 = content["images"][0]
                params = content["parameters"]
                params = json.dumps({p: params[p] for p in params if (
                    params[p] is not None and
                    params[p] != 0 and
                    params[p] is not False and
                    params[p] != "" and
                    params[p] != [] and
                    params[p] != {}
                )}, indent=2)
                image = Image.open(BytesIO(base64.b64decode(imageb64)))
                st.chat_message(last_message.name).image(image, width=512)
                with st.chat_message(last_message.name).expander("Parameters"):
                    st.code(params)
                st.session_state.messages.append(
                    BaseMessage(
                        name=last_message.name,
                        type=last_message.name,
                        content="",
                        additional_kwargs={
                            "params": params,
                            "image": image,
                        }
                    )
                )
                st.session_state.image = imageb64
