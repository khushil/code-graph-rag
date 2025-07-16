#include <stdio.h>

// Global variable
int global_counter = 0;

// Simple function
void print_hello(void) {
    printf("Hello, World!\n");
    global_counter++;
}

// Function with parameters
int add(int a, int b) {
    return a + b;
}

// Main function
int main(void) {
    print_hello();
    
    int result = add(5, 3);
    printf("5 + 3 = %d\n", result);
    
    return 0;
}