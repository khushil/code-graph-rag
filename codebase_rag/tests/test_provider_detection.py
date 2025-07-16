"""Test provider detection and configuration for multi-provider support."""

import pytest

from codebase_rag.config import detect_provider_from_model


class TestProviderDetection:
    """Test the provider detection logic."""
    
    def test_detect_gemini_provider(self):
        """Test detection of Gemini models."""
        assert detect_provider_from_model("gemini-2.5-pro") == "gemini"
        assert detect_provider_from_model("gemini-2.5-flash") == "gemini"
        assert detect_provider_from_model("gemini-2.0-flash-thinking-exp-01-21") == "gemini"
        assert detect_provider_from_model("gemini-2.5-flash-lite-preview-06-17") == "gemini"
    
    def test_detect_openai_provider(self):
        """Test detection of OpenAI models."""
        assert detect_provider_from_model("gpt-4") == "openai"
        assert detect_provider_from_model("gpt-4o") == "openai"
        assert detect_provider_from_model("gpt-4o-mini") == "openai"
        assert detect_provider_from_model("gpt-3.5-turbo") == "openai"
        assert detect_provider_from_model("o1-preview") == "openai"
        assert detect_provider_from_model("o1-mini") == "openai"
    
    def test_detect_anthropic_provider(self):
        """Test detection of Anthropic models."""
        assert detect_provider_from_model("claude-3-5-sonnet-20241022") == "anthropic"
        assert detect_provider_from_model("claude-3-5-haiku-20241022") == "anthropic"
        assert detect_provider_from_model("claude-3-opus-20240229") == "anthropic"
        assert detect_provider_from_model("claude-3-sonnet-20240229") == "anthropic"
        assert detect_provider_from_model("claude-3-haiku-20240307") == "anthropic"
    
    def test_detect_local_provider(self):
        """Test detection of local models (fallback)."""
        assert detect_provider_from_model("llama3") == "local"
        assert detect_provider_from_model("llama3.1") == "local"
        assert detect_provider_from_model("codellama") == "local"
        assert detect_provider_from_model("mistral") == "local"
        assert detect_provider_from_model("custom-model") == "local"
        assert detect_provider_from_model("") == "local"  # Empty defaults to local
    
    def test_case_sensitivity(self):
        """Test that detection is case-sensitive."""
        # Model names should be exact
        assert detect_provider_from_model("Gemini-2.5-pro") == "local"  # Capital G
        assert detect_provider_from_model("GPT-4") == "local"  # Capital GPT
        assert detect_provider_from_model("Claude-3-5-sonnet") == "local"  # Capital C


class TestProviderConfiguration:
    """Test provider configuration validation."""
    
    def test_required_api_keys(self):
        """Test that proper API keys are required for each provider."""
        from codebase_rag.config import AppConfig
        
        # Test Gemini validation
        config = AppConfig()
        config._active_orchestrator_model = "gemini-2.5-pro"
        config._active_cypher_model = "gemini-2.5-flash"
        config.GEMINI_API_KEY = None
        
        with pytest.raises(ValueError, match="GEMINI_API_KEY is required"):
            config.validate_for_usage()
        
        # Test OpenAI validation
        config = AppConfig()
        config._active_orchestrator_model = "gpt-4o"
        config._active_cypher_model = "gpt-4o-mini"
        config.OPENAI_API_KEY = None
        
        with pytest.raises(ValueError, match="OPENAI_API_KEY is required"):
            config.validate_for_usage()
        
        # Test Anthropic validation
        config = AppConfig()
        config._active_orchestrator_model = "claude-3-5-sonnet-20241022"
        config._active_cypher_model = "claude-3-5-haiku-20241022"
        config.ANTHROPIC_API_KEY = None
        
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY is required"):
            config.validate_for_usage()
    
    def test_mixed_providers(self):
        """Test configuration with mixed providers."""
        from codebase_rag.config import AppConfig
        
        config = AppConfig()
        config._active_orchestrator_model = "claude-3-5-sonnet-20241022"
        config._active_cypher_model = "gemini-2.5-flash"
        
        # Should require both API keys
        config.ANTHROPIC_API_KEY = None
        config.GEMINI_API_KEY = "test-key"
        
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY is required"):
            config.validate_for_usage()
        
        config.ANTHROPIC_API_KEY = "test-key"
        config.GEMINI_API_KEY = None
        
        with pytest.raises(ValueError, match="GEMINI_API_KEY is required"):
            config.validate_for_usage()
        
        # Should pass with both keys
        config.ANTHROPIC_API_KEY = "test-key"
        config.GEMINI_API_KEY = "test-key"
        config.validate_for_usage()  # Should not raise