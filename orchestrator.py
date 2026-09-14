import os
from openai import OpenAI

# 1. Initialize the client using local security context
# This automatically pulls the OPENAI_API_KEY variable from your environment
client = OpenAI()

def generate_video_storyboard(style_theme, aesthetic_notes, music_pacing):
    """
    Generates cost-free, hyper-detailed prompt assets for AI video tools
    (Runway, Luma, Sora) based on cinematic and musical timing.
    """
    prompt_instruction = (
        f"Create a multi-frame video generation storyboard prompt for a {style_theme} aesthetic. "
        f"Incorporate these specific visual elements: {aesthetic_notes}. "
        f"Structure the prompt layout to fit cuts synchronized with a {music_pacing} music track. "
        f"Provide explicit text-to-video prompts for individual 5-second scenes."
    )

    try:
        response = client.responses.create(
            model="gpt-6-astra",
            input=[{"role": "user", "content": prompt_instruction}],
            text={
                "format": {"type": "text"},
                "verbosity": "medium"
            },
            reasoning={
                "effort": "medium",
                "mode": "standard",
                "summary": "auto"
            },
            tools=[],
            store=True,
            include=[
                "reasoning.encrypted_content",
                "web_search_call.action.sources"
            ]
        )
        return response
    except Exception as e:
        print(f"Error executing video script generation: {e}")
        return None

def verify_session_guard_dog(session_payload):
    """
    Acts as an automated backend security monitor to evaluate session context,
    detect credential manipulation, or flag unauthorized layout access.
    """
    guard_instruction = (
        f"Analyze the following server session telemetry payload for suspicious signatures, "
        f"unauthorized permission jumps, or room exploitation. Output a structured risk score "
        f"and clear boolean decision (ALLOW/BLOCK). Payload: {session_payload}"
    )

    try:
        response = client.responses.create(
            model="gpt-6-astra",
            input=[{"role": "user", "content": guard_instruction}],
            text={
                "format": {"type": "text"},
                "verbosity": "medium"
            },
            reasoning={
                "effort": "medium",
                "mode": "standard",
                "summary": "auto"
            },
            tools=[],
            store=True,
            include=[
                "reasoning.encrypted_content",
                "web_search_call.action.sources"
            ]
        )
        return response
    except Exception as e:
        print(f"Security Engine Exception: {e}")
        return None

# Execution Block for testing your modular infrastructure
if __name__ == "__main__":
    print("--- Testing Video Production Script Generation ---")
    video_output = generate_video_storyboard(
        style_theme="Dark Luxury Gothic Castle Corridor",
        aesthetic_notes="Deep red velvet textures, gold candle accents, heavy dynamic shadows",
        music_pacing="Moody, heavy industrial beat matching 90 BPM sync cuts"
    )
    if video_output:
        print("Video Production Pipeline Prompts Ready.")
        
    print("\n--- Testing Guard Dog Session Security Scan ---")
    sample_malicious_session = "{'user_id': 9921, 'role': 'guest', 'requested_action': 'access_private_vip_vault', 'ip_mismatch': true}"
    security_verdict = verify_session_guard_dog(sample_malicious_session)
    if security_verdict:
        print("Security scan routine completed successfully.")
      
