# AutoDoc-IA Development Guidelines

## Overview
AutoDoc-IA is a Flask-based Python application for generating ETP (Estudo Técnico Preliminar) documents using OpenAI's API. The project follows a clean architecture pattern with clear separation between adapters, domain logic, and application configuration.

## Build/Configuration Instructions

### Environment Setup
1. **Environment Variables**: Copy `.env.example` to `.env` and configure:
   ```bash
   cp .env.example .env
   ```
   - Set `OPENAI_API_KEY` (required for OpenAI integration)
   - Configure `SECRET_KEY` for Flask session security
   - Adjust `HOST`, `PORT`, and logging settings as needed

2. **Dependencies**: Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   Key dependencies: Flask 3.1.1, OpenAI >=1.12.0, SQLAlchemy 2.0.41, python-docx, PyPDF2

### Development Setup
**Option 1 - Local Development:**
```bash
# Use the provided start script
chmod +x start.sh
./start.sh
```
The script automatically:
- Creates virtual environment if needed
- Copies .env.example to .env if missing
- Installs dependencies
- Attempts PostgreSQL via Docker (fallback to SQLite)
- Starts the application on http://localhost:5002

**Option 2 - Docker Development:**
```bash
# Full stack with PostgreSQL
docker-compose up

# App only (uses SQLite)
docker-compose up app
```

### Database Configuration
- **Default**: SQLite database in `database/app.db`
- **Production**: PostgreSQL via docker-compose (optional)
- **Auto-migration**: Tables are created automatically via SQLAlchemy models
- **Models**: Located in `domain/dto/` (UserDto.py, EtpDto.py)

### Application Structure
- **Entry Point**: `src/main/python/applicationApi.py`
- **Port**: 5002 (configurable via .env)
- **Static Files**: Served from `static/` directory
- **API Prefix**: All API endpoints use `/api` prefix

## Testing Information

### Test Structure
- **Test Directory**: `src/test/python/`
- **Framework**: Python unittest (built-in)
- **Test Files**: Follow pattern `test_*.py`

### Running Tests
```bash
# From project root
python3 src/test/python/test_health.py

# Or use unittest discovery
python3 -m unittest discover src/test/python
```

### Creating New Tests
Example test structure (see `src/test/python/test_health.py`):
```python
import unittest
import sys
import os

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'main', 'python'))

from application.config.FlaskConfig import create_api

class TestExample(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        os.environ['OPENAI_API_KEY'] = 'test_api_key_for_testing'
        os.environ['SECRET_KEY'] = 'test_secret_key'
        
        self.app = create_api()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
    def test_example(self):
        """Example test case"""
        response = self.client.get('/api/health')
        self.assertNotEqual(response.status_code, 404)
        
    def tearDown(self):
        """Clean up after tests"""
        # Clean environment variables
        for key in ['OPENAI_API_KEY', 'SECRET_KEY']:
            if key in os.environ:
                del os.environ[key]
```

### Test Requirements
- Always set test environment variables in setUp()
- Use Flask test client for endpoint testing
- Clean up environment variables in tearDown()
- Mock external dependencies (OpenAI API calls)

## Development Information

### Architecture Pattern
**Clean Architecture** with the following layers:
- **Adapters**: Entry points (controllers) and gateways
  - `adapter/entrypoint/`: REST controllers (ETP, User, Chat, Health)
  - `adapter/gateway/`: External service integrations
- **Domain**: Business logic and interfaces
  - `domain/dto/`: Data models (SQLAlchemy entities)
  - `domain/usecase/`: Business use cases
  - `domain/interfaces/`: Port definitions
- **Application**: Configuration and factories
  - `application/config/`: Flask and database configuration

### Key Controllers
- **EtpController**: Main ETP generation endpoints (`/api/etp`)
- **EtpDynamicController**: Dynamic ETP generation (`/api/etp-dynamic`)
- **UserController**: User management (`/api/user`)
- **ChatController**: Chat functionality (`/api/chat`)
- **HealthController**: Health checks (`/api/health`)

### Database Models
Located in `domain/dto/`:
- **User**: User management
- **EtpSession**: ETP generation sessions
- **DocumentAnalysis**: Document analysis results
- **KnowledgeBase**: Knowledge base entries
- **ChatSession**: Chat interactions
- **EtpTemplate**: ETP templates

### Development Best Practices
- **Environment Variables**: Always use .env for configuration
- **API Keys**: Never commit real API keys to repository
- **Database**: Use SQLite for development, PostgreSQL for production
- **Logging**: Configured via LOG_LEVEL environment variable
- **Static Files**: Served from root `static/` directory
- **Error Handling**: Implement proper error responses in controllers
- **CORS**: Enabled for all origins in development

### OpenAI Integration
- **Required**: Valid OPENAI_API_KEY in environment
- **Usage**: Document analysis and ETP generation
- **Models**: Configurable via application logic
- **Rate Limiting**: Consider implementing for production use

### Docker Configuration
- **Base Image**: Python 3.11-slim
- **System Dependencies**: gcc, g++ (for compiled packages)
- **Working Directory**: /app
- **Exposed Port**: 5002
- **Volume Mounts**: Application code, database, logs
- **Health Checks**: PostgreSQL service includes health checks

### Common Commands
```bash
# Start development server
python3 src/main/python/applicationApi.py

# Run with Docker
docker-compose up

# Install dependencies
pip install -r requirements.txt

# Run tests
python3 -m unittest discover src/test/python

# Check application health
curl http://localhost:5002/api/health
```

### Troubleshooting
- **Port 5002 in use**: Change PORT in .env file
- **Database issues**: Check database/ directory permissions
- **OpenAI errors**: Verify OPENAI_API_KEY is set correctly
- **Static files not served**: Check static/ directory exists and permissions
- **Import errors in tests**: Ensure proper sys.path setup in test files