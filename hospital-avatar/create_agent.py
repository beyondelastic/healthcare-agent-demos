"""Create (or update) the hospital welcome avatar agent in Microsoft Foundry.

Every run saves a new, immutable agent version; sessions use the latest.

    python create_agent.py
"""

from datetime import timedelta
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    RealtimeAudioFormatsAudioPcm,
    RealtimeFunctionToolParameters,
    VoiceAgentAudioConfig,
    VoiceAgentAudioInputConfig,
    VoiceAgentAudioOutputConfig,
    VoiceAgentAvatarConfig,
    VoiceAgentAvatarVideoBackground,
    VoiceAgentAvatarVideoParams,
    VoiceAgentAzureSemanticVadTurnDetection,
    VoiceAgentDefinition,
    VoiceAgentEchoCancellation,
    VoiceAgentFunctionTool,
    VoiceAgentInputTranscription,
    VoiceAgentNoiseReduction,
    VoiceModelType,
    VoiceOutputModality,
    VoiceType,
)

import settings
from tools import TOOL_SCHEMAS

ROOT = Path(__file__).parent


def build_definition() -> VoiceAgentDefinition:
    return VoiceAgentDefinition(
        model_type=VoiceModelType.MANAGED,
        model=settings.MODEL,
        instructions=(ROOT / "instructions.md").read_text(encoding="utf-8"),
        audio=VoiceAgentAudioConfig(
            input=VoiceAgentAudioInputConfig(
                format=RealtimeAudioFormatsAudioPcm(rate=24000),
                noise_reduction=VoiceAgentNoiseReduction(type="far_field"),
                echo_cancellation=VoiceAgentEchoCancellation(reference_source="server", channels=1),
                turn_detection=VoiceAgentAzureSemanticVadTurnDetection(
                    silence_duration_ms=timedelta(milliseconds=600), remove_filler_words=False),
                transcription=VoiceAgentInputTranscription(
                    model=settings.TRANSCRIPTION_MODEL,
                    prompt="Universitätsklinikum Musterstadt, Chirurgische Ambulanz, Radiologie, Magistrale, "
                           "Novak, Yılmaz, Kowalenko, Geburtsdatum"),
            ),
            output=VoiceAgentAudioOutputConfig(voice=settings.VOICE, voice_type=VoiceType.AZURE_STANDARD),
        ),
        avatar=VoiceAgentAvatarConfig(
            type="video_avatar", character=settings.AVATAR_CHARACTER, style=settings.AVATAR_STYLE,
            output_protocol="webrtc",
            video=VoiceAgentAvatarVideoParams(background=VoiceAgentAvatarVideoBackground(color="#FFFFFFFF")),
        ),
        output_modalities=[VoiceOutputModality.AUDIO],
        tools=[VoiceAgentFunctionTool(name=t["name"], description=t["description"],
                                      parameters=RealtimeFunctionToolParameters(t["parameters"]))
               for t in TOOL_SCHEMAS],
        store=False,
    )


def main():
    with settings.credential() as credential, AIProjectClient(
            endpoint=settings.ENDPOINT, credential=credential, allow_preview=True) as project:
        created = project.agents.create_version(
            agent_name=settings.AGENT_NAME, definition=build_definition(),
            description="Synthetic demo: welcome and wayfinding avatar at a hospital's main entrance.",
            metadata={"demo": "hospital-welcome-avatar", "synthetic_only": "true"},
        )
        print(f"Avatar agent '{settings.AGENT_NAME}' saved as version {created.version} "
              f"(model {settings.MODEL}, avatar {settings.AVATAR_CHARACTER}, voice {settings.VOICE})")


if __name__ == "__main__":
    main()
