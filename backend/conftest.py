import sys
import os

# Add the backend directory to sys.path so pytest can find modules
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)
