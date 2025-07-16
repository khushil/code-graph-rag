#ifndef MATH_UTILS_H
#define MATH_UTILS_H

// Macro definitions
#define PI 3.14159265359
#define SQUARE(x) ((x) * (x))
#define MAX(a, b) ((a) > (b) ? (a) : (b))

// Function declarations
double calculate_area(double radius);
int factorial(int n);
void swap(int* a, int* b);

// Inline function
static inline int is_even(int n) {
    return (n % 2) == 0;
}

#endif // MATH_UTILS_H