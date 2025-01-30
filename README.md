# FastAPI Starter

A starter template for building scalable and production-ready FastAPI applications with PostgreSQL and Alembic. This project is fully containerized using Docker and Docker Compose for easy setup and deployment.

## Features
- FastAPI backend
- PostgreSQL database
- Alembic for database migrations
- Docker and Docker Compose for easy setup
- JWT authentication
- Pre-configured environment variables

## Installation

### Prerequisites
Make sure you have the following installed on your machine:
- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)
- [Python 3.13](https://www.python.org/downloads/release/python-3130/)

### Clone the Repository
```sh
git clone https://github.com/yourusername/fastapi-starter.git
cd fastapi-starter
```

### Setup Environment Variables
Create a `.env` file in the root directory and copy the content from `.env.example`. Modify it if needed.

```sh
cp .env.example .env
```

### Build and Run the Project
Run the following command to build and start the containers:

```sh
docker-compose up --build
```

This will:
- Start a PostgreSQL database container
- Build and start the FastAPI backend

The application will be available at:
- **FastAPI API docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

### Running Migrations
Before using the application, run database migrations:

```sh
docker-compose exec backend alembic upgrade head
```

### Creating a Superuser
A default superuser will be created automatically using the credentials in the `.env` file. If you need to create another superuser, you can manually add it via an API call.

### Stopping the Application
To stop the application, run:
```sh
docker-compose down
```

## Project Structure
```
fastapi-starter/
│── backend/
│   ├── src/
│   │   ├── main.py          # FastAPI entry point
│   │   ├── models/          # SQLAlchemy models
│   │   ├── crud/            # Database interaction functions
│   │   ├── config/          # Configuration settings
│   ├── Dockerfile           # Backend service Dockerfile
│── docker-compose.yml       # Docker Compose configuration
│── .env                     # Environment variables
│── requirements.txt         # Dependencies
│── README.md                # Documentation
```

## API Endpoints
Once the application is running, visit [http://localhost:8000/docs](http://localhost:8000/docs) to explore available endpoints.

## Contributing
Feel free to fork this repository and customize it according to your needs. Contributions are welcome!

## License
This project is licensed under the MIT License.

