// Jest style JavaScript tests

// Production code
function fibonacci(n) {
    if (n <= 1) return n;
    return fibonacci(n - 1) + fibonacci(n - 2);
}

class StringUtils {
    static capitalize(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }
    
    static reverse(str) {
        return str.split('').reverse().join('');
    }
}

// Test suites
describe('Math Functions', () => {
    describe('fibonacci', () => {
        it('should return 0 for n=0', () => {
            expect(fibonacci(0)).toBe(0);
        });
        
        it('should return 1 for n=1', () => {
            expect(fibonacci(1)).toBe(1);
        });
        
        it('should calculate fibonacci correctly', () => {
            expect(fibonacci(5)).toBe(5);
            expect(fibonacci(10)).toBe(55);
        });
    });
});

describe('StringUtils', () => {
    beforeEach(() => {
        // Setup if needed
    });
    
    describe('capitalize', () => {
        test('should capitalize first letter', () => {
            expect(StringUtils.capitalize('hello')).toBe('Hello');
            expect(StringUtils.capitalize('world')).toBe('World');
        });
        
        test('should handle empty string', () => {
            expect(StringUtils.capitalize('')).toBe('');
        });
    });
    
    describe('reverse', () => {
        test('should reverse a string', () => {
            expect(StringUtils.reverse('hello')).toBe('olleh');
            expect(StringUtils.reverse('12345')).toBe('54321');
        });
    });
    
    afterEach(() => {
        // Cleanup if needed
    });
});