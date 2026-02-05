"""Unit tests for Bright Data LinkedIn Jobs Provider."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from src.importers.brightdata_provider import BrightDataJobProvider


@pytest.fixture
def mock_config():
    """Mock configuration for Bright Data."""
    with patch('src.importers.brightdata_provider.get_config') as mock:
        config = Mock()
        config.get_brightdata_api_key.return_value = "test_api_key"
        config.get.side_effect = lambda key, default=None: {
            "brightdata.poll_interval_seconds": 5,
            "brightdata.poll_timeout_seconds": 300
        }.get(key, default)
        mock.return_value = config
        yield config


@pytest.fixture
def provider(mock_config):
    """Create BrightDataJobProvider instance with mocked config."""
    return BrightDataJobProvider(api_key="test_api_key")


class TestBrightDataProvider:
    """Test suite for BrightDataJobProvider."""
    
    def test_init_with_api_key(self, mock_config):
        """Test initialization with explicit API key."""
        provider = BrightDataJobProvider(api_key="explicit_key")
        assert provider.api_key == "explicit_key"
        assert provider.provider_name == "brightdata"
    
    def test_init_from_config(self, mock_config):
        """Test initialization from config."""
        provider = BrightDataJobProvider()
        assert provider.api_key == "test_api_key"
    
    def test_init_missing_api_key(self):
        """Test initialization fails without API key."""
        with patch('src.importers.brightdata_provider.get_config') as mock:
            config = Mock()
            config.get_brightdata_api_key.side_effect = ValueError("API key not configured")
            mock.return_value = config
            
            with pytest.raises(ValueError, match="API key is required"):
                BrightDataJobProvider()
    
    @pytest.mark.asyncio
    async def test_trigger_search_success(self, provider):
        """Test successful search trigger."""
        mock_response = {
            "snapshot_id": "test_snapshot_123"
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_post = AsyncMock()
            mock_post.__aenter__.return_value.status = 200
            mock_post.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            
            mock_session.return_value.__aenter__.return_value.post = Mock(return_value=mock_post)
            
            snapshot_id = await provider._trigger_search(
                {"keyword": "Product Manager", "location": "United States"},
                max_results=5
            )
            
            assert snapshot_id == "test_snapshot_123"
    
    @pytest.mark.asyncio
    async def test_trigger_search_failure(self, provider):
        """Test search trigger handles API errors."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_post = AsyncMock()
            mock_post.__aenter__.return_value.status = 401
            mock_post.__aenter__.return_value.text = AsyncMock(return_value="Unauthorized")
            
            mock_session.return_value.__aenter__.return_value.post = Mock(return_value=mock_post)
            
            with pytest.raises(Exception, match="trigger failed"):
                await provider._trigger_search({}, max_results=5)
    
    @pytest.mark.asyncio
    async def test_poll_results_success(self, provider):
        """Test successful result polling."""
        mock_jobs = [
            {"job_title": "Product Manager", "company_name": "TechCorp"},
            {"job_title": "Senior PM", "company_name": "StartupInc"}
        ]
        
        with patch('aiohttp.ClientSession') as mock_session:
            # Simulate 202 (processing), then 200 (ready)
            mock_get_processing = AsyncMock()
            mock_get_processing.__aenter__.return_value.status = 202
            
            mock_get_ready = AsyncMock()
            mock_get_ready.__aenter__.return_value.status = 200
            mock_get_ready.__aenter__.return_value.json = AsyncMock(return_value=mock_jobs)
            
            session_mock = mock_session.return_value.__aenter__.return_value
            session_mock.get = Mock(side_effect=[mock_get_processing, mock_get_ready])
            
            jobs = await provider._poll_results("test_snapshot_123")
            
            assert len(jobs) == 2
            assert jobs[0]["job_title"] == "Product Manager"
    
    @pytest.mark.asyncio
    async def test_poll_results_timeout(self, provider):
        """Test polling timeout."""
        provider.poll_timeout = 1  # 1 second timeout
        provider.poll_interval = 0.5  # 0.5 second intervals
        
        with patch('aiohttp.ClientSession') as mock_session:
            # Always return 202 (processing)
            mock_get = AsyncMock()
            mock_get.__aenter__.return_value.status = 202
            
            mock_session.return_value.__aenter__.return_value.get = Mock(return_value=mock_get)
            
            with pytest.raises(TimeoutError, match="polling timeout"):
                await provider._poll_results("test_snapshot_123")
    
    def test_normalize_job_standard_fields(self, provider):
        """Test job normalization with standard fields."""
        raw_job = {
            "job_title": "Senior Product Manager",
            "company_name": "TechCorp",
            "job_location": "San Francisco, CA",
            "job_summary": "Great PM role",
            "url": "https://linkedin.com/jobs/123",
            "job_posted_date": "2024-02-01T10:00:00Z",
            "job_function": "Product Management",
            "job_industries": "Technology, Software",
            "job_seniority_level": "5 years",
            "job_base_pay_range": "$120k - $150k"
        }
        
        normalized = provider.normalize_job(raw_job)
        
        assert normalized['title'] == "Senior Product Manager"
        assert normalized['company'] == "TechCorp"
        assert normalized['location'] == "San Francisco, CA"
        assert normalized['description'] == "Great PM role"
        assert normalized['url'] == "https://linkedin.com/jobs/123"
        assert normalized['salary'] == "$120k - $150k"
        assert normalized['source'] == "brightdata"
        assert "Product Management" in normalized['required_skills']
        assert normalized['experience_required'] == 5.0
    
    def test_normalize_job_salary_extraction(self, provider):
        """Test that Bright Data's salary field is properly extracted."""
        raw_job = {
            "job_title": "PM",
            "company_name": "CompanyX",
            "job_base_pay_range": "$100,000 - $130,000/yr"
        }
        
        normalized = provider.normalize_job(raw_job)
        
        assert normalized['salary'] == "$100,000 - $130,000/yr"
    
    def test_normalize_job_date_parsing(self, provider):
        """Test date parsing."""
        raw_job = {
            "job_title": "PM",
            "company_name": "CompanyX",
            "job_posted_date": "2024-02-05T15:30:00Z"
        }
        
        normalized = provider.normalize_job(raw_job)
        
        assert isinstance(normalized['posting_date'], datetime)
        assert normalized['posting_date'].year == 2024
        assert normalized['posting_date'].month == 2
        assert normalized['posting_date'].day == 5
    
    def test_normalize_job_missing_fields(self, provider):
        """Test normalization handles missing fields gracefully."""
        raw_job = {
            "job_title": "PM",
            "company_name": "CompanyX"
        }
        
        normalized = provider.normalize_job(raw_job)
        
        assert normalized['title'] == "PM"
        assert normalized['company'] == "CompanyX"
        assert isinstance(normalized['posting_date'], datetime)
        assert 'required_skills' in normalized
        assert normalized['source'] == "brightdata"
    
    @pytest.mark.asyncio
    async def test_search_jobs_async_integration(self, provider):
        """Test full search_jobs_async workflow."""
        mock_snapshot_id = "snapshot_123"
        mock_jobs = [{"job_title": "PM", "company_name": "Corp"}]
        
        with patch.object(provider, '_trigger_search', new_callable=AsyncMock) as mock_trigger, \
             patch.object(provider, '_poll_results', new_callable=AsyncMock) as mock_poll:
            
            mock_trigger.return_value = mock_snapshot_id
            mock_poll.return_value = mock_jobs
            
            jobs = await provider.search_jobs_async(
                keywords="Product Manager",
                location="US",
                max_results=5
            )
            
            assert len(jobs) == 1
            assert jobs[0]["job_title"] == "PM"
            mock_trigger.assert_called_once()
            mock_poll.assert_called_once_with(mock_snapshot_id, None)
    
    @pytest.mark.asyncio
    async def test_search_jobs_with_progress_callback(self, provider):
        """Test search with progress callback."""
        messages = []
        
        async def progress_callback(msg, progress):
            messages.append((msg, progress))
        
        with patch.object(provider, '_trigger_search', new_callable=AsyncMock) as mock_trigger, \
             patch.object(provider, '_poll_results', new_callable=AsyncMock) as mock_poll:
            
            mock_trigger.return_value = "snapshot_123"
            mock_poll.return_value = [{"job_title": "PM"}]
            
            await provider.search_jobs_async(
                keywords="PM",
                max_results=5,
                progress_callback=progress_callback
            )
            
            assert len(messages) > 0
            assert any("Triggering" in msg for msg, _ in messages)
            assert any("Fetched" in msg for msg, _ in messages)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
