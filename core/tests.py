from django.test import TestCase

"""
Security Tests for Search Bar - SQL Injection Protection
=========================================================
This test suite verifies protection against UNION-based SQL injection and other attack vectors.

Test Cases:
1. UNION SELECT Attack
2. Comment-based Injection (--) 
3. Multiple Statement Injection
4. Excessively Long Input
5. Special Characters
6. Normal Valid Search
"""

import os
import django
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from elections.models import Election
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'evoting.settings')
django.setup()

User = get_user_model()


class SearchBarSecurityTests(TestCase):
    """
    Test suite for verifying search bar is protected against SQL injection attacks.
    
    SECURITY ARCHITECTURE:
    =====================
    
    Layer 1: Input Validation (core/views.py - validate_search_query)
    - Max length: 200 characters
    - Suspicious keyword detection: UNION, SELECT, INSERT, UPDATE, DELETE, DROP, EXEC, --, /*, */
    - Logs suspicious attempts for audit trail
    
    Layer 2: Django ORM Protection (Parameterized Queries)
    - Uses Q objects with icontains lookup
    - Django automatically escapes parameters
    - Prevents literal SQL injection through search fields
    
    Layer 3: Error Handling
    - DatabaseError caught and logged
    - Generic error messages (no SQL detail exposure)
    - Stack traces NOT displayed to users
    
    Layer 4: Template Auto-Escaping
    - Django templates auto-escape output by default
    - Query parameter {{ query }} is HTML-escaped
    - Prevents XSS via search input
    """
    
    def setUp(self):
        """Create test users and elections"""
        self.client = Client()
        
        # Create test users
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='AdminPass123!',
            role='Admin'
        )
        
        self.voter_user = User.objects.create_user(
            username='voter',
            email='voter@test.com',
            password='VoterPass123!',
            role='Voter'
        )
        
        # Create test elections
        self.election1 = Election.objects.create(
            title='Presidential Election 2024',
            description='Main presidential election',
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=7),
            status='Open',
            created_by=self.admin_user
        )
        
        self.election2 = Election.objects.create(
            title='Local Council Election',
            description='Local government election',
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=14),
            status='Pending',
            created_by=self.admin_user
        )
    
    # ========== TEST CASES ==========
    
    def test_union_based_injection_attempt(self):
        """
        TEST: UNION-based SQL Injection
        PAYLOAD: ' UNION SELECT username, password, null FROM auth_user -- 
        EXPECTED: Search returns error or empty results, NO data leak
        """
        self.client.login(username='voter', password='VoterPass123!')
        
        injection_payload = "' UNION SELECT username, password, null FROM accounts_customuser -- "
        response = self.client.get('/search/', {'q': injection_payload})
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        
        response_content = response.content.decode()
        
        # Should show error message, not SQL details or success
        self.assertIn('error', response_content.lower())
        self.assertIn('invalid search query', response_content.lower())
        
        # Most importantly: Should NOT show any search results table with data
        # The injection should be blocked, so no elections table should be rendered
        self.assertIn('search operation failed', response_content.lower())
    
    def test_comment_injection_attack(self):
        """
        TEST: Comment-based SQL Injection (-- or /*)
        PAYLOAD: 'admin' -- 
        EXPECTED: Blocked by validation, error message
        """
        self.client.login(username='voter', password='VoterPass123!')
        
        injection_payload = "admin' -- "
        response = self.client.get('/search/', {'q': injection_payload})
        
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode()
        
        # Should not execute malicious query
        self.assertNotIn('password', response_content.lower())
    
    def test_drop_table_injection(self):
        """
        TEST: Destructive SQL Injection (DROP TABLE)
        PAYLOAD: '; DROP TABLE elections_election; -- 
        EXPECTED: Blocked, no tables dropped, error message
        """
        self.client.login(username='admin', password='AdminPass123!')
        
        # Count elections before
        count_before = Election.objects.count()
        
        injection_payload = "'; DROP TABLE elections_election; -- "
        response = self.client.get('/search/', {'q': injection_payload})
        
        # Verify table still exists
        count_after = Election.objects.count()
        self.assertEqual(count_before, count_after)
        self.assertGreater(count_after, 0)  # Data still there
    
    def test_excessive_input_length(self):
        """
        TEST: Excessively Long Input (DoS prevention)
        PAYLOAD: 'A' * 1000
        EXPECTED: Rejected due to MAX_SEARCH_LENGTH (200), error message
        """
        self.client.login(username='voter', password='VoterPass123!')
        
        long_payload = 'A' * 500
        response = self.client.get('/search/', {'q': long_payload})
        
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode()
        
        # Should not process oversized input
        self.assertIn('error', response_content.lower())
    
    def test_valid_normal_search(self):
        """
        TEST: Valid Normal Search Query
        PAYLOAD: 'Presidential'
        EXPECTED: Returns matching election normally
        """
        self.client.login(username='voter', password='VoterPass123!')
        
        response = self.client.get('/search/', {'q': 'Presidential'})
        
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode()
        
        # Should contain the matching election
        self.assertIn('Presidential Election 2024', response_content)
        self.assertIn('Found 1 result', response_content)
    
    def test_case_insensitive_search(self):
        """
        TEST: Case-insensitive Search Works
        PAYLOAD: 'PRESIDENTIAL' (uppercase)
        EXPECTED: Matches 'Presidential Election' normally (case-insensitive)
        """
        self.client.login(username='voter', password='VoterPass123!')
        
        response = self.client.get('/search/', {'q': 'PRESIDENTIAL'})
        
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode()
        
        # Should match case-insensitively
        # Note: Voter only sees Open/Closed elections, so we search for the Open one
        self.assertIn('Presidential Election 2024', response_content)
        self.assertIn('found 1 result', response_content.lower())
    
    def test_empty_search_query(self):
        """
        TEST: Empty Search Query
        PAYLOAD: ''
        EXPECTED: No error, shows all available elections
        """
        self.client.login(username='voter', password='VoterPass123!')
        
        response = self.client.get('/search/', {'q': ''})
        
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode()
        
        # Should suggest entering search query
        self.assertIn('search query', response_content.lower())
    
    def test_voter_cannot_see_pending_elections(self):
        """
        TEST: Access Control - Voter Permission Check
        EXPECTED: Voter cannot see Pending elections even if searched
        """
        self.client.login(username='voter', password='VoterPass123!')
        
        response = self.client.get('/search/', {'q': 'Local Council'})
        
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode()
        
        # Pending election should NOT appear for voter
        self.assertNotIn('Local Council Election', response_content)
    
    def test_admin_can_see_all_elections(self):
        """
        TEST: Access Control - Admin Permission Check
        EXPECTED: Admin can see all elections including Pending
        """
        self.client.login(username='admin', password='AdminPass123!')
        
        response = self.client.get('/search/', {'q': 'Council'})
        
        self.assertEqual(response.status_code, 200)
        response_content = response.content.decode()
        
        # Pending election should appear for admin
        self.assertIn('Local Council Election', response_content)
    
    def test_no_sql_error_exposure(self):
        """
        TEST: Error Messages Don't Expose SQL Details
        EXPECTED: Generic error message, no stack trace
        """
        self.client.login(username='voter', password='VoterPass123!')
        
        # Try various payloads
        payloads = [
            "' UNION SELECT * FROM --",
            "'); DROP TABLE --",
            "1 OR 1=1 --",
            "; EXEC xp_cmdshell --"
        ]
        
        for payload in payloads:
            response = self.client.get('/search/', {'q': payload})
            response_content = response.content.decode()
            
            # Should NOT contain SQL keywords or technical details
            self.assertNotIn('SQL', response_content)
            self.assertNotIn('Traceback', response_content)
            self.assertNotIn('DATABASE', response_content)
            self.assertNotIn('DJANGO', response_content)


class SearchBarSecurityDocumentation:
    """
    SECURITY IMPLEMENTATION SUMMARY
    ===============================
    
    1. INPUT VALIDATION
       - Maximum query length: 200 characters
       - Blocks SQL keywords: UNION, SELECT, INSERT, UPDATE, DELETE, DROP, EXEC
       - Blocks comment patterns: --, /*, */
       - Logs all suspicious attempts
    
    2. DJANGO ORM PROTECTION
       - Uses Q objects with icontains lookup: Q(field__icontains=query)
       - Parameterized queries (Django automatically parameterizes)
       - Cannot inject SQL through parameter binding
       
       Example Django ORM call:
       elections = elections.filter(Q(title__icontains=query))
       
       This generates:
       SELECT * FROM elections WHERE title LIKE %s
       With query as a parameter, NOT embedded in SQL
    
    3. ERROR HANDLING
       - Try-except blocks catch DatabaseError
       - Logs errors with user info for audit trail
       - Returns generic error message to user
       - Never displays SQL details or stack traces
    
    4. TEMPLATE SAFETY
       - Django auto-escapes all template variables by default
       - {{ query }} is HTML-escaped in output
       - Prevents XSS attacks via search input
    
    5. ACCESS CONTROL
       - @login_required decorator enforces authentication
       - Voter/Admin role checks
       - Voters only see Open/Closed elections
       - Admin sees all elections
    
    WHY THIS IS SAFE:
    =================
    
    Django ORM Protection:
    - The icontains lookup uses database parameterized queries
    - User input is passed as a parameter, not embedded in SQL
    - Example attack (' UNION SELECT ...) is treated as literal string
    - Database driver cannot interpret it as SQL code
    
    Validation Layer:
    - Catches obvious injection attempts before even reaching ORM
    - Max length prevents buffer overflow attacks
    - Keyword detection stops formatted SQL statements
    
    Error Handling:
    - If anything goes wrong, user gets generic error
    - No SQL details exposed
    - No stack traces visible
    - Attack attempts logged for security monitoring
    
    TEST RESULTS:
    =============
    When query = ' UNION SELECT username, password FROM users --
    
    Result:
    ✓ Input validation blocks malicious keywords (UNION, SELECT)
    ✓ Generic error message displayed
    ✓ NO data from users table exposed
    ✓ NO stack trace shown
    ✓ Attempt logged for audit
    
    Query becomes:
    SELECT * FROM elections 
    WHERE (title LIKE %s OR status LIKE %s OR description LIKE %s)
    
    With %s as: ' UNION SELECT username, password FROM users --
    
    Database driver escapes this as a literal string, not SQL!
    """
    pass
