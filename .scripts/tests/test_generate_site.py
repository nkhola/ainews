import os
import sys
import tempfile
import ast
import shutil
import pytest
from unittest.mock import patch, MagicMock

# Add the .scripts directory to the Python path
script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, script_dir)

# Import the module under test
import generate_site

def test_syntax_is_valid():
    """Verify that the generate_site.py file contains valid Python syntax."""
    file_path = os.path.join(script_dir, 'generate_site.py')
    with open(file_path, 'r', encoding='utf-8') as f:
        source_code = f.read()
    
    # ast.parse will raise a SyntaxError if the code is invalid
    try:
        ast.parse(source_code)
    except SyntaxError as e:
        pytest.fail(f"Syntax error in generate_site.py: {e}")

@patch('generate_site.NewsCrawler')
@patch('generate_site.FinanceCrawler')
@patch('generate_site.MasterCompiler')
def test_generate_daily_briefing(MockMasterCompiler, MockFinanceCrawler, MockNewsCrawler):
    """Test the main generation function to ensure it creates the expected files."""
    # Setup mock returns
    mock_compiler = MockMasterCompiler.return_value
    mock_compiler.synthesize_news.return_value = "Mocked Markdown Content"
    
    mock_news_crawler = MockNewsCrawler.return_value
    mock_news_crawler.get_latest_news.return_value = [{"title": "AI News", "content": "..."}]
    
    mock_fin_crawler = MockFinanceCrawler.return_value
    mock_fin_crawler.get_latest_news.return_value = [{"title": "Fin News", "content": "..."}]

    # Create a temporary directory to act as the repo root
    with tempfile.TemporaryDirectory() as temp_repo_root:
        # Patch the paths in generate_site to point to our temp directory
        original_dirname = os.path.dirname
        
        def mock_dirname(path):
            if path == os.path.abspath(generate_site.__file__):
                # Return a dummy script dir
                return os.path.join(temp_repo_root, ".scripts")
            elif path.endswith(".scripts"):
                # Return the temp repo root
                return temp_repo_root
            return original_dirname(path)
            
        with patch('os.path.dirname', side_effect=mock_dirname):
            # Also mock os.chdir to prevent actually changing directory
            with patch('os.chdir'):
                try:
                    generate_site.generate_daily_briefing()
                except Exception as e:
                    pytest.fail(f"generate_daily_briefing raised an exception: {e}")
        
        # Verify files were created
        files_created = os.listdir(temp_repo_root)
        
        # We expect index.html and one daily briefing file
        assert "index.html" in files_created
        
        html_files = [f for f in files_created if f.endswith('.html') and f != 'index.html']
        assert len(html_files) == 1
        
        # Check that the index.html file has content
        with open(os.path.join(temp_repo_root, "index.html"), 'r') as f:
            index_content = f.read()
            assert "The Post-Human Briefing" in index_content
            assert html_files[0] in index_content # the daily file should be linked
