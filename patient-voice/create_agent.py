"""Create (or update) the patient discharge voice agent in Microsoft Foundry.

Every run saves a new, immutable agent version; the endpoint uses the latest.

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
        # No fixed greeting: app.py starts each session in the language the patient selected.
        audio=VoiceAgentAudioConfig(
            input=VoiceAgentAudioInputConfig(
                format=RealtimeAudioFormatsAudioPcm(rate=24000),
                noise_reduction=VoiceAgentNoiseReduction(type="far_field"),
                echo_cancellation=VoiceAgentEchoCancellation(reference_source="server", channels=1),
                turn_detection=VoiceAgentAzureSemanticVadTurnDetection(
                    silence_duration_ms=timedelta(milliseconds=600),
                    remove_filler_words=False,
                ),
                transcription=VoiceAgentInputTranscription(
                    model=settings.TRANSCRIPTION_MODEL,
                    prompt="Entlassbrief, Gallenblase, Ibuprofen, Pantoprazol, Ramipril, Chirurgische Ambulanz",
                ),
            ),
            output=VoiceAgentAudioOutputConfig(voice=settings.VOICE, voice_type=VoiceType.AZURE_STANDARD),
        ),
        output_modalities=[VoiceOutputModality.AUDIO],
        tools=[
            VoiceAgentFunctionTool(name=t["name"], description=t["description"],
                                   parameters=RealtimeFunctionToolParameters(t["parameters"]))
            for t in TOOL_SCHEMAS
        ],
        store=False,
    )


def main():
    with settings.credential() as credential, AIProjectClient(
            endpoint=settings.ENDPOINT, credential=credential, allow_preview=True) as project:
        created = project.agents.create_version(
            agent_name=settings.AGENT_NAME, definition=build_definition(),
            description="Synthetic demo: explains an approved discharge letter by voice; staff hand-off.",
            metadata={"demo": "patient-discharge-voice", "synthetic_only": "true"},
        )
        print(f"Voice agent '{settings.AGENT_NAME}' saved as version {created.version} "
              f"(model {settings.MODEL}, voice {settings.VOICE}, transcription {settings.TRANSCRIPTION_MODEL})")


if __name__ == "__main__":
    main()
