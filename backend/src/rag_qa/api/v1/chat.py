from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from rag_qa.api.deps import get_current_user, get_db
from rag_qa.core.exceptions import NotFoundException
from rag_qa.models.conversation import Conversation, Message, MessageRole
from rag_qa.models.user import User
from rag_qa.schemas.chat import ChatRequest, ChatResponse, ConversationResponse, FeedbackCreate
from rag_qa.schemas.common import ResponseBase

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ResponseBase[ChatResponse])
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if request.conversation_id is None:
        conversation = Conversation(
            user_id=current_user.id,
            project_id=request.project_id,
            title=request.question[:50],
        )
        db.add(conversation)
        await db.flush()
        request.conversation_id = conversation.id
    else:
        result = await db.execute(
            select(Conversation).where(Conversation.id == request.conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise NotFoundException(message="Conversation not found")

    user_message = Message(
        conversation_id=request.conversation_id,
        role=MessageRole.USER,
        content=request.question,
    )
    db.add(user_message)
    await db.flush()

    if request.stream:
        async def event_generator():
            assistant_message = Message(
                conversation_id=request.conversation_id,
                role=MessageRole.ASSISTANT,
                content="",
            )
            db.add(assistant_message)
            await db.flush()
            answer_text = "This is a streamed response placeholder."
            for char in answer_text:
                yield {"event": "message", "data": json.dumps({"content": char})}
            assistant_message.content = answer_text
            await db.commit()
            yield {"event": "done", "data": json.dumps({"message_id": assistant_message.id})}

        return EventSourceResponse(event_generator())

    assistant_message = Message(
        conversation_id=request.conversation_id,
        role=MessageRole.ASSISTANT,
        content="This is a response placeholder.",
    )
    db.add(assistant_message)
    await db.commit()
    await db.flush()

    return ResponseBase(
        data=ChatResponse(
            conversation_id=request.conversation_id,
            message_id=assistant_message.id,
            answer=assistant_message.content,
        )
    )


@router.get("/conversations", response_model=ResponseBase[list[ConversationResponse]])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    conversations = result.scalars().all()
    return ResponseBase(data=[ConversationResponse.model_validate(c) for c in conversations])


@router.get("/conversations/{conversation_id}", response_model=ResponseBase[ConversationResponse])
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise NotFoundException(message="Conversation not found")
    return ResponseBase(data=ConversationResponse.model_validate(conversation))


@router.post(
    "/conversations/{conversation_id}/messages/{message_id}/feedback",
    response_model=ResponseBase,
)
async def submit_feedback(
    conversation_id: str,
    message_id: str,
    feedback_in: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Message).where(Message.id == message_id, Message.conversation_id == conversation_id)
    )
    message = result.scalar_one_or_none()
    if message is None:
        raise NotFoundException(message="Message not found")
    message.feedback_type = feedback_in.feedback_type
    message.feedback_comment = feedback_in.comment
    await db.commit()
    return ResponseBase()
