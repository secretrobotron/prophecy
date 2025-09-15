#!/usr/bin/env python3
"""
Example usage of the AI Providers system.

This script demonstrates how to use the AI provider system to send prompts
to different AI services (starting with ChatGPT) and get responses back.
"""

import os
from prophecy import AIProviderFactory, AIProviderError
from prophecy.prompts import Prompts
from prophecy.stories import Stories
from prophecy.bible import Bible


def demonstrate_ai_provider_basic_usage():
    """Demonstrate basic AI provider usage."""
    print("=== Basic AI Provider Usage ===\n")
    
    # Check for API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("⚠️  OpenAI API key not found in environment variable OPENAI_API_KEY")
        print("   Setting a mock key for demonstration (will fail on actual API calls)\n")
        api_key = "mock_key_for_demo"
    
    try:
        # Create AI provider using factory
        ai_provider = AIProviderFactory.create_provider(
            'chatgpt',
            api_key=api_key,
            model='gpt-3.5-turbo',
            max_tokens=500,
            temperature=0.7
        )
        
        print(f"✓ Created AI provider: {ai_provider.get_provider_name()}")
        print(f"✓ Configuration valid: {ai_provider.validate_configuration()}")
        
        # Show available providers
        available = AIProviderFactory.get_available_providers()
        print(f"✓ Available providers: {', '.join(available)}\n")
        
        # Example prompt
        test_prompt = """
        Analyze the following biblical narrative and identify the main themes:
        
        "In the beginning God created the heaven and the earth. And the earth was without form, 
        and void; and darkness was upon the face of the deep. And the Spirit of God moved upon 
        the face of the waters. And God said, Let there be light: and there was light."
        """
        
        print("--- Sending test prompt to AI ---")
        print(f"Prompt: {test_prompt.strip()[:100]}...")
        
        # This will fail without real API key, but demonstrates the interface
        if api_key != "mock_key_for_demo":
            try:
                response = ai_provider.post_prompt(
                    test_prompt,
                    system_message="You are a biblical scholar and literary analyst."
                )
                print(f"✓ AI Response: {response[:200]}...")
            except AIProviderError as e:
                print(f"✗ AI Error: {e}")
        else:
            print("⚠️  Skipping actual AI call due to mock API key")
            
    except AIProviderError as e:
        print(f"✗ Provider creation failed: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")


def demonstrate_integration_with_prophecy():
    """Demonstrate AI provider integration with Prophecy components."""
    print("\n=== Integration with Prophecy Components ===\n")
    
    try:
        # Initialize Prophecy components
        prompts = Prompts()
        stories = Stories()
        bible = Bible()
        
        print(f"✓ Loaded {prompts.get_prompt_count()} prompts")
        print(f"✓ Loaded {len(stories.titles)} stories")
        print(f"✓ Bible component ready")
        
        # Get a specific story and prompt
        story = stories.get_story('The Creation')
        prompt_data = prompts.get_prompt_by_id('1')
        
        # Get biblical text for the story
        biblical_text = bible.get_text(story.book, *story.to_bible_parts())
        
        # Limit text length for demonstration
        if len(biblical_text) > 800:
            biblical_text = biblical_text[:800] + "..."
        
        print(f"\n--- Story: {story.title} ---")
        print(f"Book: {story.book}")
        print(f"Verses: {story.verses}")
        print(f"Text length: {len(biblical_text)} characters")
        
        print(f"\n--- Using Prompt #{prompt_data['id']} ---")
        print(f"Period: {prompt_data['period']}")
        print(f"Topic: {prompt_data['topic']}")
        print(f"Prompt: {prompt_data['prompt'][:100]}...")
        
        # Create populated template
        populated_template = prompts.populate_template(prompt_data, story, biblical_text)
        
        print(f"\n--- Populated Template ---")
        print(f"Template length: {len(populated_template)} characters")
        print("Template preview:")
        print("-" * 50)
        print(populated_template[:400] + "..." if len(populated_template) > 400 else populated_template)
        print("-" * 50)
        
        # Check for API key
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            try:
                # Create AI provider
                ai_provider = AIProviderFactory.create_provider('chatgpt', api_key=api_key)
                
                print(f"\n--- Sending to AI Provider ---")
                print("Sending populated template to ChatGPT...")
                
                # Send to AI
                ai_response = ai_provider.post_prompt(
                    populated_template,
                    system_message="You are a biblical scholar analyzing ancient texts."
                )
                
                print(f"✓ AI Analysis Complete!")
                print(f"Response length: {len(ai_response)} characters")
                print("\nAI Response:")
                print("=" * 60)
                print(ai_response)
                print("=" * 60)
                
            except AIProviderError as e:
                print(f"✗ AI Provider Error: {e}")
        else:
            print("\n⚠️  Set OPENAI_API_KEY environment variable to test AI integration")
            
    except Exception as e:
        print(f"✗ Integration error: {e}")


def demonstrate_extensibility():
    """Demonstrate how to extend the AI provider system."""
    print("\n=== Extensibility Example ===\n")
    
    # Show how to register a custom provider
    from prophecy.ai_providers import AIProvider
    
    class MockAIProvider(AIProvider):
        """Example custom AI provider."""
        
        def post_prompt(self, prompt: str, **kwargs) -> str:
            # Simple mock response
            return f"Mock AI response to: {prompt[:50]}... [This is a demonstration]"
        
        def validate_configuration(self) -> bool:
            return True
    
    # Register the custom provider
    AIProviderFactory.register_provider('mock', MockAIProvider)
    
    print("✓ Registered custom 'mock' provider")
    print(f"✓ Available providers: {', '.join(AIProviderFactory.get_available_providers())}")
    
    # Use the custom provider
    mock_provider = AIProviderFactory.create_provider('mock')
    response = mock_provider.post_prompt("Test prompt for custom provider")
    
    print(f"✓ Custom provider response: {response}")
    print("\nThis demonstrates how easy it is to add new AI providers!")


def main():
    """Run all demonstrations."""
    print("=" * 70)
    print("🔮 PROPHECY AI PROVIDER SYSTEM DEMONSTRATION")
    print("=" * 70)
    
    demonstrate_ai_provider_basic_usage()
    demonstrate_integration_with_prophecy()
    demonstrate_extensibility()
    
    print(f"\n{'=' * 70}")
    print("✨ Demonstration complete!")
    print("💡 To test with real AI: export OPENAI_API_KEY=your_api_key")
    print("=" * 70)


if __name__ == "__main__":
    main()