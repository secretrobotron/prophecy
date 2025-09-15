#!/usr/bin/env python3
"""
Example usage of the Prompts class.

This script demonstrates how to use the Prompts class to access prompts data
and populate templates with biblical stories and text.
"""

from prophecy.prompts import Prompts
from prophecy.stories import Stories
from prophecy.bible import Bible


def main():
    """Demonstrate the Prompts class functionality."""
    print("=== Prompts Class Usage Example ===\n")
    
    # Initialize the Prompts class
    # Uses PROPHECY_DATA_FOLDER environment variable or defaults to 'data'
    prompts = Prompts()
    
    print(f"Loaded {prompts.get_prompt_count()} prompts")
    print(f"Available periods: {prompts.get_periods()}")
    print(f"Available topics: {len(prompts.get_topics())} unique topics\n")
    
    # Example 1: Access specific prompts
    print("--- Example 1: Accessing prompts ---")
    
    # Get a specific prompt by ID
    prompt = prompts.get_prompt_by_id('1')
    print(f"Prompt #{prompt['id']}:")
    print(f"  Period: {prompt['period']}")
    print(f"  Topic: {prompt['topic']}")
    print(f"  Text: {prompt['prompt']}\n")
    
    # Filter prompts by period
    babylonian_prompts = prompts.get_prompts_by_period('Babylonian')
    print(f"Found {len(babylonian_prompts)} Babylonian prompts")
    
    # Filter prompts by topic
    topic_prompts = prompts.get_prompts_by_topic('Geopolitical Danger')
    print(f"Found {len(topic_prompts)} prompts about 'Geopolitical Danger'\n")
    
    # Example 2: Template population
    print("--- Example 2: Template population ---")
    
    # Set up other components for full workflow
    stories = Stories()
    bible = Bible()
    
    # Get a story and its biblical text
    story = stories.get_story('The Creation')
    text = bible.get_text(story.book, *story.to_bible_parts())
    
    # Limit text for demonstration
    if len(text) > 500:
        text = text[:500] + "..."
    
    print(f"Using story: {story.title}")
    print(f"Biblical text: {len(text)} characters\n")
    
    # Populate the template
    result = prompts.populate_template(prompt, story, text)
    
    print("Generated template output:")
    print("-" * 50)
    print(result)
    print("-" * 50)
    
    # Verify line folding
    lines = result.split('\n')
    max_line_length = max(len(line) for line in lines)
    print(f"\nTemplate statistics:")
    print(f"  Total length: {len(result)} characters")
    print(f"  Number of lines: {len(lines)}")
    print(f"  Maximum line length: {max_line_length} characters")
    print(f"  Line folding: {'✓ PASSED' if max_line_length <= 100 else '✗ FAILED'}")
    
    print("\n=== Example completed successfully ===")


if __name__ == "__main__":
    main()