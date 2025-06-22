from unittest.mock import patch
from app.services.scraping_service import ScrapingService

@patch('app.services.scraping_service.ScrapingService._scrape_google', return_value=[])
@patch('app.services.scraping_service.ScrapingService._scrape_bing', return_value=[])
@patch('requests.get')
def test_scrape_web_duckduckgo_only(mock_get, mock_bing, mock_google, app):
    """Test DuckDuckGo scraping with mocked JSON response"""

    mock_get.return_value.json.return_value = {
        'AbstractText': 'Test abstract',
        'AbstractURL': 'http://example.com',
        'Heading': 'Test Heading',
        'RelatedTopics': [
            {
                'Text': 'Test topic - description',
                'FirstURL': 'http://example.com/topic'
            },
            {
                'Text': 'Another topic - description 2',
                'FirstURL': 'http://example.com/topic2'
            }
        ]
    }

    with app.app_context():
        results = ScrapingService.scrape_web('test query', limit=10)

        assert len(results) == 3

        titles = [r['title'] for r in results]
        urls = [r['url'] for r in results]

        assert 'Test Heading' in titles
        assert 'Test topic' in titles
        assert 'Another topic' in titles

        assert 'http://example.com' in urls
        assert 'http://example.com/topic' in urls
        assert 'http://example.com/topic2' in urls
