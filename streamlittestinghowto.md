Introduction
Streamlit is a popular open-source Python framework among data scientists and AI/ML engineers for its ability to quickly build interactive web applications with just a few lines of code. Streamlit’s simplicity and rapid prototyping features make it ideal for visualizing data and building proof-of-concept models.

However, testing becomes essential as projects grow and the code base becomes more complex. Proper testing ensures that changes do not introduce bugs, allowing for smoother updates and preventing breaking changes.

What is App Testing?
App Testing is evaluating and verifying that a software application functions as intended. Tests are crucial for identifying bugs, ensuring good performance, and validating the app’s functionality before it reaches production.

Testing methods generally fall into two categories:

Manual: Testers manually execute test cases without the use of automated tools. This type of testing is useful in the early stages of development. Testers can perform ad-hoc testing to explore unforeseen scenarios and behaviors that automated testing might not cover.
Automatic: Using scripts and tools to execute pre-defined test cases. It is particularly beneficial for projects with frequent code changes, as it efficiently executes repetitive tests, regression testing, and load testing. Automated testing will be covered in more detail later.
Types of Tests
Testing can be categorized into two main types: Unit Tests and Integration Tests.

Unit Tests: These tests check if individual components operate correctly. Think of it as inspecting each ingredient before baking — you want to ensure every ingredient is fresh and of good quality. If a unit test fails, you replace or adjust the problematic component.
Integration Tests: These tests check how multiple components work together. They are like combining all the ingredients to bake a cake. After ensuring each ingredient (unit test) is up to standard, integration tests confirm that all components work well together.
Testing a Basic Streamlit Application
Consider the following Streamlit application:

"""app.py"""

import streamlit as st

def add(a, b):
    return a+b

st.title("Simple Addition App")

a = st.number_input("Enter first number", 0, 100)
b = st.number_input("Enter second number", 0, 100)

if st.button("Add"):
    result = add(a, b)
    st.markdown(f"The result is {result}")
To run the application, use:

streamlit run app.py
This will open the following web application in your browser (RHS):


The left-hand side displays the code, while the right-hand side illustrates which part of the web application each code segment corresponds to
This simple interactive web application allows users to input two numbers and click the “Add” button to sum them. To ensure the app functions correctly, we need to simulate user interactions and verify the functionality of the add function. In the remaining parts of this article, I will be introducing Pytest to streamline the process.

What is Pytest?
In this article, we explore how to use the pytest library—a powerful Python testing framework—to write and automate the execution of test cases.

Installation of Pytest
To start using pytest, install it in your Streamlit development environment with the following command:

pip install pytest
Pytest Structure
One of Pytest’s strengths is its ability to automatically identify test files and functions based on naming conventions:

Test File Naming: Pytest looks for files starting with test_ or ending with _test. Examples include test_example.py or example_test.py.
Test Function Naming: Within these files, Pytest recognizes test functions that start with test_. For example, a function named test_feature will be detected as a test function.
Files or functions not adhering to these conventions will not be recognized, and there is no built-in method to change this behavior.

Example Project Structure
An example of what your project structure might look like:


Testing the app
1. Initialize the simulated app and execute the first script run

Start by initializing the Streamlit application for testing:

from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py").run()
2. Simulate user interaction

You can simulate user interactions by indexing the widgets in the order they appear in the application. For instance:

# Simulate the user incrementing the first number input three times
at.number_input[0].increment().run()
at.number_input[0].increment().run()
at.number_input[0].increment().run()

# Simulate the user incrementing the first number input one time
at.number_input[1].increment().run()

# Simulate the user clicking the "Add" button
at.button[0].click().run()
Alternatively, you can use the “key” name to access the elements:

a = st.number_input("Enter first number", key="First element", 0, 100)
b = st.number_input("Enter second number", key="Second element", 0, 100)

at.number_input(key="First element").increment().run()
at.number_input(key="Second element").increment().run()
3. Assertions

Finally, use assert statements to verify that the application displays the correct information:

assert at.markdown[0].value == "The result is 4"
Add these code chunks (1. to 3.) into a test function, as shown below:


Illustrates how every code segment in the test function connects to specific features within the web application
4. Running the Test

To run the test script, simply execute pytest in your terminal. The output will display a summary of the tests that have passed or failed. In the event of a test failure, Pytest provides detailed information indicating which part of your test code was incorrect.

Example:


Passed test case

Failed test case
Types of Assertion Call
When testing Streamlit widgets, you can use assertion calls to verify their properties and user interactions. Here’s an example using the st.multiselect function:

import streamlit as st

st.multiselect(
    label="Letters",
    options=['A', 'B', 'C', 'D', 'E']
    default=None,
    key="multiselect_element",
    help="Pick one or more letter(s)",
    on_change=None,
    args=None,
    kwargs=None,
    max_selections=3,
    placeholder="Choose an option",
    disabled=False,
    label_visibility="visible"
)
To test this widget, you can use the following assertions:

# Simulate the user selecting the options 'A' and 'C' from the multiselect widget
at.multiselect(key="multiselect_element").select(['A', 'C']) 

# Use assertions to check if the widget behaves as expected
assert at.multiselect(key="multiselect_element").value[0] == ['A', 'C']
assert at.multiselect(key="multiselect_element").label == "Letters"
assert at.multiselect(key="multiselect_element").options == ['A', 'B', 'C', 'D', 'E']
assert at.multiselect(key="multiselect_element").default == []
assert at.multiselect(key="multiselect_element").help == "Pick one or more letter(s)"
assert at.multiselect(key="multiselect_element").placeholder == "Choose an option"
assert at.multiselect(key="multiselect_element").disabled == False
Fixtures and Parametrization
To make your test codes more efficient, fixtures and parametrization can be used to build comprehensive and efficient test suits. These techniques ensure that various test cases are covered without redundant code, improving the robustness and maintainability of your tests.

Fixtures
Fixtures in testing frameworks such as Pytest enable you to create a consistent environment for your tests. They contribute to a predictable and regulated environment by establishing preconditions, such as initializing database connections or creating test data. By using fixtures, you can write the setup code once and reuse it across several tests, ensuring that each test starts with the same initial setup.

To use Pytest fixtures, define a fixture with the @pytest.fixture decorator:

@pytest.fixture
def numbers():
    """Defining a fixture"""
    return 10, 20

def test_add(numbers):
    """
    Args:
    - numbers: A tuple containing the numbers (10, 20) provided by the fixture.

    Asserts:
    - The result of add(10, 20) should be 30.
    """
    a, b = numbers
    result = add(a, b)
    assert result == 30 # 10 + 20
In this example, the numbers fixture is defined which returns a tuple (10, 20) that will be used in test_add(). Pytest automatically recognizes numbers as a fixture, looks for a fixture with that name, and injects its return value into the test function. This can then be used to perform assertions and verify that the code behaves as expected.

Parametrization
Parametrization allows you to run the same test function with different sets of data. This feature is useful for ensuring that your code behaves correctly across a range of input values or conditions. It helps validate that your code handles various scenarios as expected without needing to write multiple similar test functions for each input scenario.

Here’s how you can use the @pytest.mark.parametrize decorator to run a test function with different input values:

@pytest.mark.parametrize(
    "a, b, expected_result",
    [
        (2, 5, 7),  # Test case 1
        (4, 6, 10), # Test case 2
        (5, 7, 12)  # Test case 3
    ]
)
def test_add(a, b, expected_result):
    """
    Args:
    - a: First number.
    - b: Second number.
    - expected_result: The expected result of a + b.
    
    Assert:
    - The result of add(a, b) should match the expected_result.
    """
    result = add(a, b)
    assert result == expected_result
In this example, the names of the parameters are in a string and a list of tuples is given where each tuple represents a different set of inputs and the expected result. The test_add will be executed once for each set of parameters provided.

Mocking and Patching
Mocking and patching are advanced techniques in testing that help improve the efficiency and effectiveness of your test code, especially when dealing with external dependencies.

Mocking is used in unit testing to isolate the unit being tested from its external dependencies. By replacing real objects with mock objects, you can ensure that the behavior of these dependencies does not affect your tests. The unittest.mock library provides tools to create mock objects and make assertions about their usage.
Patching refers to temporarily replacing a real object with a mock, such as replacing functions, classes, or methods in a module during testing. The @patch decorator is used to mock an object, replacing it with a mock during the execution of the test.
Example
Consider the following Streamlit application:

"""utils.py"""

import requests

def fetch_data(query: str) -> Tuple[int, int]:
    """Simulates fetching data based on the query"""
    response = requests.get(query)
    data = response.json()
    a, b = data['a'], data['b']
    return a, b

def add(a: int, b: int) -> int:
    return a+b
"""app.py"""

import streamlit as st
from utils import fetch_data, add

st.title('Simple Calculation App')

a, b = fetch_data(query)

result = add(a, b)

st.markdown(f"The results is {result}.")
In this example, we have an application that uses the fetch_data function that takes a query, sends a request and returns a tuple (a, b). The Streamlit app then adds the two values to return a string markdown format. However, when testing, we want to isolate the functionality of our application without relying on the actual fetch_data function, which performs external network requests. This is where mocking and patching come into play.

"""test_app.py"""

@patch('utils.fetch_data')
def test_app(
    mock_fetch_data: Mock
) -> None:
    # Set up mock function return value
    mock_fetch_data.return_value = (3, 4)
    
    # Create an instance of the Streamlit app
    at = AppTest.from_file("app.py").run()

    # Verify that the mocked functions were called with the expected arguments
    mock_fetch_data.assert_called_once

    # Verify that the results are displayed correctly
    expected_output = "The result is 7"

    assert at.markdown[0].value == expected_output
The @patch decorator replaces the real fetch_data function from the utils module with a mock object during the test. This prevents the actual network request and uses the mock object instead.
Then, we fix the return value of fetch_data to (3, 4), representing a and b respectively.
The test creates an instance of the Streamlit app and runs it. Since fetch_data is mocked, the actual network request is bypassed, and the mock return value is used.
The assert_called_once() method checks that fetch_data was called exactly once. The assert statement verifies that the output displayed in the Streamlit app matches the expected result, "The result is 7".
Handling Multiple User Interactions
When your Streamlit application involves different combinations of user interactions, you can test multiple scenarios within a single test case. Consider the following application, which requires users to enter a password to gain access:

"""utils.py"""

def check_password():
    """
    Renders a password UI and checks if the user had the correct password.

    Returns:
    - bool: True if the password is correct and False otherwise
    """
    def password_entered():
        if hmac.compare_digest(st.session_state["password"], PASSWORD):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.text_input(
        "Enter the password 🔒", type="password", on_change=password_entered, key="password"
    )

    if "password_correct" in st.session_state:
        st.error("😕 Password incorrect")

    return False
"""app.py"""

if not check_password():
    st.stop()

st.title("Simple Addition App")

When user key in the wrong password
In this example, the application prompts users for a password before displaying the main content. To test different scenarios where the user inputs both incorrect and correct passwords, use the following approach:

"""test_app.py"""

def test_password():
    # Set the correct password
    with patch('utils.PASSWORD', 'abc'):
        """
        Test case 1: User input incorrect password
        - An error will be returned
        """
        at = AppTest.from_file("app.py").run()
        
        # Simulate the user keying the incorrect password
        at.text_input[0].input("123").run()
    
        # Assert the results
        assert "😕 Password incorrect" in at.error[0].value
    
        """
        Test case 2: User input correct password
        - The app's title is displayed
        """
        # Simulate user keying the correct password
        at.text_input[0].input("abc").run()
        
        # Assert the results
        assert "Simple Addition App" in at.title[0].value
Use @patch to set the correct password for the test.
Test case 1: Simulate entering an incorrect password and verify that the error message is shown.
Test case 2: Simulate entering the correct password and check that the app’s title appears.
Automating the Running of Tests
Now that you have written your test scripts, to ensure that your application functions as expected whenever you make changes and push them to your remote repository, you can automate testing. This can be achieved through various methods, with two common approaches being:

Pre-push hook
Integrating pytest with Continuous Integration (CI)
Adding pytest to Dockerfile (not recommended as it may be hard to get the logs)
Note: There are other ways to integrate automated testing that are not covered in this article.

Adding Pytest to Dockerfile
# ... Rest of your Dockerfile

# Copy test files into the container
COPY tests/ tests/

# Run pytest to execute tests
RUN pytest

# ... Rest of your Dockerfile
COPY tests/ tests/: This line copies the test files from your local tests directory into the container’s tests directory.
RUN pytest: This line runs pytest inside the container to execute the tests. If any test fails, the Docker build process will indicate an error, allowing us to address issues before deploying the container.
Adding a Test Stage to the CI/CD Pipeline
Integrating pytest into your CI/CD pipeline ensures that tests are automatically executed during the build process whenever code changes are pushed. Here’s an example configuration for adding a test stage in a CI/CD pipeline (e.g., /.github/workflows/run_test.yml):

"""run_test.yml"""

# ... Rest of your YAML file

jobs:
  build:
    # ... Rest of your YAML file

    steps:
      # ... Rest of your YAML file
  
      - name: Test with pytest
        run: |
          pytest
steps: Defines steps within the build job.
- name: Test with pytest: A descriptive label for the step.
run: | pytest: The run keyword specifies the shell command to execute during this step. In this case, it runs the pytest command.
Conclusion
Automated testing is an essential part of ensuring the reliability and functionality of Streamlit applications. By leveraging tools like Pytest, you can efficiently run both basic and sophisticated test scenarios to validate user interactions and application behavior.

