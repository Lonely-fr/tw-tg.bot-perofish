def place_streetlights(n, a, x, b, y):
    """
    Алгоритм автоматического размещения фонарей для освещения улицы
    
    n - количество домов на улице
    a - количество фонарей типа A
    x - сила свечения фонарей типа A (освещает 2*x+1 домов)
    b - количество фонарей типа B  
    y - сила свечения фонарей типа B (освещает 2*y+1 домов)
    
    Возвращает:
    - "NO" если невозможно осветить всю улицу
    - "YES" и оптимальное размещение фонарей если возможно
    """
    
    # Вычисляем зону покрытия каждого типа фонарей
    coverage_a = 2 * x + 1  # Фонарь типа A освещает себя и по x домов с каждой стороны
    coverage_b = 2 * y + 1  # Фонарь типа B освещает себя и по y домов с каждой стороны
    
    # Максимально возможное покрытие при использовании всех фонарей
    max_coverage = a * coverage_a + b * coverage_b
    
    # Если даже с максимальным покрытием не можем осветить все дома
    if max_coverage < n:
        return "NO", []
    
    # Создаем массив для отслеживания освещенности домов
    street = [0] * n  # 0 - не освещен, 1 - освещен
    
    # Список для хранения позиций фонарей
    lights_positions = []
    
    # Жадный алгоритм размещения фонарей
    # Сначала размещаем фонари с большим радиусом действия
    lights_types = []
    for _ in range(a):
        lights_types.append(('A', x))
    for _ in range(b):
        lights_types.append(('B', y))
    
    # Сортируем по убыванию силы свечения
    lights_types.sort(key=lambda item: item[1], reverse=True)
    
    # Для каждого фонаря находим оптимальную позицию
    for light_type, power in lights_types:
        coverage = 2 * power + 1
        best_position = -1
        max_new_coverage = -1
        
        # Ищем позицию, которая освещает максимум новых домов
        for pos in range(n):
            new_coverage = 0
            # Подсчитываем сколько новых домов будет освещено в этой позиции
            start_house = max(0, pos - power)
            end_house = min(n - 1, pos + power)
            
            for house in range(start_house, end_house + 1):
                if street[house] == 0:  # Если дом еще не освещен
                    new_coverage += 1
            
            if new_coverage > max_new_coverage:
                max_new_coverage = new_coverage
                best_position = pos
        
        # Размещаем фонарь на лучшей позиции
        if best_position != -1:
            lights_positions.append((light_type, best_position))
            # Отмечаем освещенные дома
            start_house = max(0, best_position - power)
            end_house = min(n - 1, best_position + power)
            for house in range(start_house, end_house + 1):
                street[house] = 1
    
    # Проверяем, все ли дома освещены
    if sum(street) == n:
        return "YES", lights_positions
    else:
        # Если не все дома освещены, пробуем другие стратегии размещения
        # Например, более плотное размещение
        
        # Очищаем предыдущие результаты
        street = [0] * n
        lights_positions = []
        
        # Альтернативная стратегия - равномерное распределение
        # Распределяем фонари равномерно по улице
        total_lights = a + b
        if total_lights > 0:
            interval = n // total_lights
            
            light_idx = 0
            for i in range(total_lights):
                position = min(i * interval + interval // 2, n - 1)
                
                if light_idx < a:
                    # Используем фонарь типа A
                    lights_positions.append(('A', position))
                    power = x
                    light_idx += 1
                else:
                    # Используем фонарь типа B
                    lights_positions.append(('B', position))
                    power = y
                
                # Отмечаем освещенные дома
                start_house = max(0, position - power)
                end_house = min(n - 1, position + power)
                for house in range(start_house, end_house + 1):
                    street[house] = 1
            
            if sum(street) == n:
                return "YES", lights_positions
        
        return "NO", []

def print_result(result, positions, n):
    """Вывод результата размещения фонарей"""
    status, lights = result
    print(status)
    
    if status == "YES":
        print(f"Оптимальное размещение {len(lights)} фонарей:")
        for light_type, position in lights:
            print(f"Фонарь типа {light_type} на позиции {position}")
        
        # Визуализация размещения
        street_visual = ["."] * n
        for light_type, position in lights:
            street_visual[position] = f'{light_type}'
        print("Схема размещения:", "".join(f"[{cell}]" for cell in street_visual))

# Пример использования
if __name__ == "__main__":
    # Ввод данных (можно заменить на чтение из файла или другого источника)
    print("Введите параметры улицы:")
    n = int(input("Количество домов (n): "))  # Количество домов
    a = int(input("Количество фонарей типа A (a): "))  # Количество фонарей типа A
    x = int(input("Сила свечения фонарей типа A (x): "))  # Сила свечения фонарей типа A
    b = int(input("Количество фонарей типа B (b): "))  # Количество фонарей типа B
    y = int(input("Сила свечения фонарей типа B (y): "))  # Сила свечения фонарей типа B
    
    # Запуск алгоритма размещения фонарей
    result = place_streetlights(n, a, x, b, y)
    print_result(result, [], n)