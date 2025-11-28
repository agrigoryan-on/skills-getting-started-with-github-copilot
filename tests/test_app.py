"""
Tests for the Mergington High School API
"""

import pytest
from fastapi.testclient import TestClient
from src.app import app, activities


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_activities():
    """Reset activities data before each test"""
    # Store original state
    original_activities = {
        name: {
            "description": details["description"],
            "schedule": details["schedule"],
            "max_participants": details["max_participants"],
            "participants": details["participants"].copy()
        }
        for name, details in activities.items()
    }
    
    yield
    
    # Restore original state after test
    for name, details in original_activities.items():
        activities[name]["participants"] = details["participants"].copy()


class TestRootEndpoint:
    """Tests for the root endpoint"""
    
    def test_root_redirects_to_index(self, client):
        """Test that root endpoint redirects to static index.html"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/index.html"


class TestGetActivities:
    """Tests for the GET /activities endpoint"""
    
    def test_get_activities_returns_200(self, client):
        """Test that getting activities returns 200"""
        response = client.get("/activities")
        assert response.status_code == 200
    
    def test_get_activities_returns_dict(self, client):
        """Test that activities endpoint returns a dictionary"""
        response = client.get("/activities")
        data = response.json()
        assert isinstance(data, dict)
    
    def test_get_activities_has_required_fields(self, client):
        """Test that each activity has required fields"""
        response = client.get("/activities")
        data = response.json()
        
        for activity_name, details in data.items():
            assert "description" in details
            assert "schedule" in details
            assert "max_participants" in details
            assert "participants" in details
            assert isinstance(details["participants"], list)
            assert isinstance(details["max_participants"], int)
    
    def test_get_activities_contains_expected_activities(self, client):
        """Test that response contains some expected activities"""
        response = client.get("/activities")
        data = response.json()
        
        assert "Chess Club" in data
        assert "Programming Class" in data
        assert "Basketball Team" in data


class TestSignupForActivity:
    """Tests for the POST /activities/{activity_name}/signup endpoint"""
    
    def test_signup_success(self, client):
        """Test successful signup for an activity"""
        response = client.post(
            "/activities/Chess%20Club/signup?email=newstudent@mergington.edu"
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "newstudent@mergington.edu" in data["message"]
        assert "Chess Club" in data["message"]
    
    def test_signup_adds_participant(self, client):
        """Test that signup actually adds participant to activity"""
        email = "teststudent@mergington.edu"
        client.post(f"/activities/Chess%20Club/signup?email={email}")
        
        # Verify participant was added
        response = client.get("/activities")
        data = response.json()
        assert email in data["Chess Club"]["participants"]
    
    def test_signup_duplicate_participant(self, client):
        """Test that signing up twice returns error"""
        email = "duplicate@mergington.edu"
        
        # First signup
        response1 = client.post(f"/activities/Chess%20Club/signup?email={email}")
        assert response1.status_code == 200
        
        # Second signup (duplicate)
        response2 = client.post(f"/activities/Chess%20Club/signup?email={email}")
        assert response2.status_code == 400
        data = response2.json()
        assert "already signed up" in data["detail"].lower()
    
    def test_signup_nonexistent_activity(self, client):
        """Test signup for activity that doesn't exist"""
        response = client.post(
            "/activities/Nonexistent%20Activity/signup?email=test@mergington.edu"
        )
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_signup_without_email(self, client):
        """Test signup without providing email parameter"""
        response = client.post("/activities/Chess%20Club/signup")
        assert response.status_code == 422  # Validation error


class TestRemoveParticipant:
    """Tests for the DELETE /activities/{activity_name}/remove endpoint"""
    
    def test_remove_participant_success(self, client):
        """Test successful removal of a participant"""
        # First add a participant
        email = "removeme@mergington.edu"
        client.post(f"/activities/Chess%20Club/signup?email={email}")
        
        # Then remove them
        response = client.delete(f"/activities/Chess%20Club/remove?email={email}")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert email in data["message"]
    
    def test_remove_participant_actually_removes(self, client):
        """Test that remove actually removes participant from activity"""
        email = "willberemoved@mergington.edu"
        
        # Add participant
        client.post(f"/activities/Chess%20Club/signup?email={email}")
        
        # Remove participant
        client.delete(f"/activities/Chess%20Club/remove?email={email}")
        
        # Verify participant was removed
        response = client.get("/activities")
        data = response.json()
        assert email not in data["Chess Club"]["participants"]
    
    def test_remove_nonexistent_participant(self, client):
        """Test removing a participant that isn't signed up"""
        response = client.delete(
            "/activities/Chess%20Club/remove?email=notregistered@mergington.edu"
        )
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_remove_from_nonexistent_activity(self, client):
        """Test removing from activity that doesn't exist"""
        response = client.delete(
            "/activities/Fake%20Activity/remove?email=test@mergington.edu"
        )
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_remove_without_email(self, client):
        """Test remove without providing email parameter"""
        response = client.delete("/activities/Chess%20Club/remove")
        assert response.status_code == 422  # Validation error


class TestActivityCapacity:
    """Tests for activity capacity and availability"""
    
    def test_activity_respects_max_participants(self, client):
        """Test that activities have max participant limits"""
        response = client.get("/activities")
        data = response.json()
        
        for activity_name, details in data.items():
            assert len(details["participants"]) <= details["max_participants"]
    
    def test_signup_and_remove_workflow(self, client):
        """Test complete workflow: signup, verify, remove, verify"""
        email = "workflow@mergington.edu"
        activity = "Programming Class"
        
        # Get initial count
        response = client.get("/activities")
        initial_count = len(response.json()[activity]["participants"])
        
        # Signup
        client.post(f"/activities/{activity}/signup?email={email}")
        response = client.get("/activities")
        assert len(response.json()[activity]["participants"]) == initial_count + 1
        
        # Remove
        client.delete(f"/activities/{activity}/remove?email={email}")
        response = client.get("/activities")
        assert len(response.json()[activity]["participants"]) == initial_count


class TestDataIntegrity:
    """Tests for data integrity and validation"""
    
    def test_activity_structure_consistency(self, client):
        """Test that all activities have consistent structure"""
        response = client.get("/activities")
        data = response.json()
        
        required_keys = {"description", "schedule", "max_participants", "participants"}
        
        for activity_name, details in data.items():
            assert set(details.keys()) == required_keys
    
    def test_participants_are_valid_emails(self, client):
        """Test that existing participants have email format"""
        response = client.get("/activities")
        data = response.json()
        
        for activity_name, details in data.items():
            for participant in details["participants"]:
                assert "@" in participant
                assert "." in participant
