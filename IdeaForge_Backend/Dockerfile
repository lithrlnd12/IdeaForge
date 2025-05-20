# Use the official Python image.
FROM python:3.10-slim

# Install git
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create a non-root user
RUN useradd -m -u 1000 appuser

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Change ownership of the app directory
RUN chown -R appuser:appuser /app /opt/venv

# Switch to non-root user
USER appuser

# Set global git user/email for appuser
RUN git config --global user.email "ideaforge-bot@example.com" && git config --global user.name "IdeaForge Bot"

# Expose port 8080 for Cloud Run
EXPOSE 8080

# Run the Flask app
CMD ["python", "live_backend.py"] 