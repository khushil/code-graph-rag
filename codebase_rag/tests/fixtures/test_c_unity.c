#include "unity.h"
#include <string.h>

// Production code
int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

int is_prime(int n) {
    if (n <= 1) return 0;
    for (int i = 2; i * i <= n; i++) {
        if (n % i == 0) return 0;
    }
    return 1;
}

char* string_reverse(char* str) {
    int len = strlen(str);
    for (int i = 0; i < len / 2; i++) {
        char temp = str[i];
        str[i] = str[len - 1 - i];
        str[len - 1 - i] = temp;
    }
    return str;
}

// Test setup and teardown
void setUp(void) {
    // Set up test environment
}

void tearDown(void) {
    // Clean up after test
}

// Test functions
void test_factorial_base_cases(void) {
    TEST_ASSERT_EQUAL_INT(1, factorial(0));
    TEST_ASSERT_EQUAL_INT(1, factorial(1));
}

void test_factorial_positive_numbers(void) {
    TEST_ASSERT_EQUAL_INT(6, factorial(3));
    TEST_ASSERT_EQUAL_INT(24, factorial(4));
    TEST_ASSERT_EQUAL_INT(120, factorial(5));
}

void test_is_prime_small_numbers(void) {
    TEST_ASSERT_FALSE(is_prime(0));
    TEST_ASSERT_FALSE(is_prime(1));
    TEST_ASSERT_TRUE(is_prime(2));
    TEST_ASSERT_TRUE(is_prime(3));
    TEST_ASSERT_FALSE(is_prime(4));
    TEST_ASSERT_TRUE(is_prime(5));
}

void test_is_prime_larger_numbers(void) {
    TEST_ASSERT_TRUE(is_prime(17));
    TEST_ASSERT_TRUE(is_prime(23));
    TEST_ASSERT_FALSE(is_prime(24));
    TEST_ASSERT_FALSE(is_prime(100));
}

void test_string_reverse(void) {
    char str1[] = "hello";
    TEST_ASSERT_EQUAL_STRING("olleh", string_reverse(str1));
    
    char str2[] = "12345";
    TEST_ASSERT_EQUAL_STRING("54321", string_reverse(str2));
    
    char str3[] = "a";
    TEST_ASSERT_EQUAL_STRING("a", string_reverse(str3));
}

// Main test runner
int main(void) {
    UNITY_BEGIN();
    
    RUN_TEST(test_factorial_base_cases);
    RUN_TEST(test_factorial_positive_numbers);
    RUN_TEST(test_is_prime_small_numbers);
    RUN_TEST(test_is_prime_larger_numbers);
    RUN_TEST(test_string_reverse);
    
    return UNITY_END();
}