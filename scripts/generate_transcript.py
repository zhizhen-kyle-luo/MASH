#!/usr/bin/env python3
"""
Script to generate a conversation transcript from a MASH session
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.utils.logger import TranscriptLogger


def format_transcript_html(transcript_data: dict) -> str:
    """Generate an HTML-formatted transcript"""
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>MASH Transcript - {transcript_data['case_id']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
        .message {{ margin: 10px 0; padding: 15px; border-radius: 5px; }}
        .user {{ background-color: #e3f2fd; border-left: 5px solid #2196f3; }}
        .agent {{ background-color: #f3e5f5; border-left: 5px solid #9c27b0; }}
        .concierge {{ background-color: #e8f5e8; border-left: 5px solid #4caf50; }}
        .urgent-care {{ background-color: #fff3e0; border-left: 5px solid #ff9800; }}
        .insurance {{ background-color: #e0f2f1; border-left: 5px solid #009688; }}
        .coordinator {{ background-color: #fce4ec; border-left: 5px solid #e91e63; }}
        .timestamp {{ color: #666; font-size: 0.9em; }}
        .speaker {{ font-weight: bold; margin-bottom: 5px; }}
        .content {{ line-height: 1.6; }}
        .final-plan {{ background-color: #fff9c4; padding: 20px; border-radius: 5px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>MASH Conversation Transcript</h1>
        <p><strong>Case ID:</strong> {transcript_data['case_id']}</p>
        <p><strong>Session ID:</strong> {transcript_data['session_id']}</p>
        <p><strong>Timestamp:</strong> {transcript_data['timestamp']}</p>
        <p><strong>Status:</strong> {transcript_data['status']}</p>
        <p><strong>Total Turns:</strong> {transcript_data['turn_count']}</p>
    </div>
"""

    for msg in transcript_data['messages']:
        timestamp = msg.get('timestamp', 'Unknown')
        speaker = msg.get('speaker', 'unknown')
        agent = msg.get('agent', '').lower()
        content = msg.get('content', '')

        if speaker == 'user':
            css_class = 'user'
            speaker_name = 'USER'
        else:
            css_class = agent if agent else 'agent'
            speaker_name = (agent or 'SYSTEM').upper()

        html += f"""
    <div class="message {css_class}">
        <div class="speaker">{speaker_name}</div>
        <div class="timestamp">{timestamp}</div>
        <div class="content">{content}</div>
    </div>
"""

    if transcript_data.get('final_plan'):
        html += f"""
    <div class="final-plan">
        <h3>Final Plan</h3>
        <pre>{json.dumps(transcript_data['final_plan'], indent=2)}</pre>
    </div>
"""

    html += """
</body>
</html>
"""
    return html


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Generate transcript from MASH session")
    parser.add_argument("session_id", help="Session ID to generate transcript for")
    parser.add_argument("--format", choices=["json", "html"], default="json",
                       help="Output format")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")

    args = parser.parse_args()

    try:
        # Load transcript
        transcript_logger = TranscriptLogger(args.session_id)
        messages = transcript_logger.get_transcript()

        if not messages:
            print(f"No transcript found for session: {args.session_id}", file=sys.stderr)
            sys.exit(1)

        # Create transcript data structure
        transcript_data = {
            "session_id": args.session_id,
            "case_id": "unknown",
            "timestamp": datetime.now().isoformat(),
            "status": "completed",
            "turn_count": len(messages),
            "messages": messages,
            "final_plan": None
        }

        # Generate output based on format
        if args.format == "html":
            output = format_transcript_html(transcript_data)
        else:  # json
            output = json.dumps(transcript_data, indent=2, default=str)

        # Write output
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
            print(f"Transcript written to: {args.output}")
        else:
            print(output)

    except Exception as e:
        print(f"Error generating transcript: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()