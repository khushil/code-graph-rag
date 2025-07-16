Feature: Calculator Operations
  As a user
  I want to perform basic arithmetic operations
  So that I can calculate results quickly

  Background:
    Given I have a calculator

  @arithmetic @basic
  Scenario: Addition of two numbers
    Given I have entered 50 into the calculator
    And I have entered 70 into the calculator
    When I press add
    Then the result should be 120 on the screen

  @arithmetic @basic
  Scenario: Subtraction of two numbers
    Given I have entered 100 into the calculator
    And I have entered 25 into the calculator
    When I press subtract
    Then the result should be 75 on the screen

  @arithmetic
  Scenario Outline: Multiplication operations
    Given I have entered <first> into the calculator
    And I have entered <second> into the calculator
    When I press multiply
    Then the result should be <result> on the screen

    Examples:
      | first | second | result |
      | 2     | 3      | 6      |
      | 5     | 10     | 50     |
      | 7     | 8      | 56     |

  @error-handling
  Scenario: Division by zero
    Given I have entered 10 into the calculator
    And I have entered 0 into the calculator
    When I press divide
    Then I should see an error message "Cannot divide by zero"