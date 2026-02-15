import requests
import pandas as pd
from datetime import datetime
import time
import os
import json

# КОНФИГУРАЦИЯ
LOGIN_URL = "https://www.tipstrr.com/login"
API_LIST_URL = "https://tipstrr.com/api/portfolio/freguli/tips/completed"
API_TIP_URL = "https://tipstrr.com/api/portfolio/freguli/tips/cached"
API_FIXTURE_URL = "https://tipstrr.com/api/fixture"
USERNAME = "kzgansta@gmail.com"
PASSWORD = "gmaMob8989bl!"


def create_session():
    """Создает сессию с авторизацией на сайте"""
    session = requests.Session()

    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://tipstrr.com/tipster/freguli/results',
    })

    print("1. Получаем начальные куки...")
    session.get("https://www.tipstrr.com")

    print("2. Логинимся...")
    login_data = {"username": USERNAME, "password": PASSWORD}

    login_headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'https://www.tipstrr.com',
        'Referer': 'https://www.tipstrr.com/login',
    }

    response = session.post(LOGIN_URL, data=login_data, headers=login_headers)

    if response.status_code != 200:
        print(f"Ошибка авторизации! Статус: {response.status_code}")
        if response.history:
            print("Был редирект, возможно авторизация успешна")
        else:
            return None

    print("✓ Авторизация успешна!")
    return session


def calculate_correct_profit(odds, result_code):
    """
    Рассчитывает правильный профит на основе коэффициента и результата
    result_code: 1=Win, 2=Loss, 3=Void, 4=Unknown(4), 5=Unknown(5)
    Если кф 4.6 и выигрыш, то профит = 4.6 - 1 = 3.6
    Если ставка проиграла, Void или Unknown(4): профит = -1
    Unknown(5): профит = 0 (возврат ставки)
    """
    # Преобразуем odds в float
    try:
        odds_float = float(odds) if odds else 0
    except (ValueError, TypeError):
        odds_float = 0

    if result_code == 1:  # Win
        return odds_float - 1 if odds_float > 0 else 0
    elif result_code == 5:  # Unknown(5) - возврат ставки
        return 0.0
    else:  # Loss (2), Void (3), Unknown(4) - все -1
        return -1.0


def get_result_text(result_code):
    """
    Преобразует код результата в текст
    result_code: 1=Win, 2=Lose, 3=Lose (Void), 4=Lose (Unknown), 5=Unknown(5)
    """
    if result_code == 1:
        return "Win"
    elif result_code == 2:
        return "Lose"
    elif result_code == 3:
        return "Lose"  # Void показываем как Lose
    elif result_code == 4:
        return "Lose"  # Unknown(4) показываем как Lose
    elif result_code == 5:
        return "Unknown(5)"
    else:
        return f"Unknown ({result_code})"


def parse_tip_details(session, reference, fixture_reference):
    """Парсит детали прогноза и матча"""
    try:
        # 1. Получаем детали прогноза (ставки)
        tip_url = f"{API_TIP_URL}/{reference}"
        response_tip = session.get(tip_url)

        if response_tip.status_code != 200:
            print(f"  Ошибка при запросе прогноза {reference}: {response_tip.status_code}")
            return None

        tip_data = response_tip.json()

        # 2. Получаем детали матча (фикстуры)
        fixture_data = None
        if fixture_reference:
            fixture_url = f"{API_FIXTURE_URL}/{fixture_reference}"
            response_fixture = session.get(fixture_url)

            if response_fixture.status_code == 200:
                fixture_data = response_fixture.json()

        return extract_tip_data(tip_data, fixture_data, reference)

    except Exception as e:
        print(f"  Ошибка при парсинге {reference}: {e}")
        return None


def extract_tip_data(tip_data, fixture_data, reference):
    """Извлекает данные из JSON ответов"""
    # Основные данные из прогноза
    title = tip_data.get('title', '')
    tip_date = tip_data.get('tipDate', '')
    result = tip_data.get('result', '')
    original_profit = tip_data.get('profit', '')

    # Обработка даты
    event_date = ''
    event_time = ''
    if tip_date:
        try:
            dt = datetime.fromisoformat(tip_date.replace('Z', '+00:00'))
            event_date = dt.strftime('%Y-%m-%d')
            event_time = dt.strftime('%H:%M')
        except:
            event_date = tip_date[:10] if len(tip_date) >= 10 else tip_date
            event_time = ''

    # Данные о ставке
    odds = None
    market_text = ''
    bet_text = ''

    if tip_data.get('tipBet') and len(tip_data['tipBet']) > 0:
        odds = tip_data['tipBet'][0].get('odds', '')

    if tip_data.get('tipBetItem') and len(tip_data['tipBetItem']) > 0:
        market_text = tip_data['tipBetItem'][0].get('marketText', '')
        bet_text = tip_data['tipBetItem'][0].get('betText', '')

    # Данные о матче из фикстуры (если есть)
    home_team = ''
    away_team = ''
    sport = ''
    league = ''

    if fixture_data:
        home_team = fixture_data.get('homeTeam', {}).get('name', '')
        away_team = fixture_data.get('awayTeam', {}).get('name', '')
        sport = fixture_data.get('sport', {}).get('name', '')
        league = fixture_data.get('competition', {}).get('name', '')

    # Если нет данных из фикстуры, пробуем извлечь из title
    if not home_team and ' v ' in title:
        parts = title.split(' v ')
        if len(parts) == 2:
            home_team = parts[0].strip()
            away_team = parts[1].strip()

    # Определяем текст результата
    result_text = get_result_text(result)

    # РАСЧЕТ ПРАВИЛЬНОГО ПРОФИТА
    # Используем нашу функцию calculate_correct_profit вместо данных с сайта
    correct_profit = calculate_correct_profit(odds, result)

    return {
        'event_date': event_date,
        'event_time': event_time,
        'home_team': home_team,
        'away_team': away_team,
        'match': f"{home_team} vs {away_team}" if home_team and away_team else title,
        'sport': sport,
        'league': league,
        'market': market_text,
        'bet': bet_text,
        'odds': odds,
        'result': result_text,
        'profit': correct_profit,  # Используем правильный расчет
        'original_profit': original_profit,  # Сохраняем оригинальный для сравнения
        'raw_result_code': result,
        'reference': reference
    }


def get_fixture_reference_from_tip(session, reference):
    """Получает fixtureReference из данных прогноза"""
    tip_url = f"{API_TIP_URL}/{reference}"
    response = session.get(tip_url)

    if response.status_code == 200:
        tip_data = response.json()
        if tip_data.get('tipBetItem') and len(tip_data['tipBetItem']) > 0:
            return tip_data['tipBetItem'][0].get('fixtureReference')

    return None


def main():
    print("=== Парсер Tipstrr.com ===")
    print("=" * 30)

    # Запрашиваем количество прогнозов
    while True:
        try:
            user_input = input(
                "\nСколько прогнозов парсить? (Enter = ВСЕ доступные, число = конкретное количество): ").strip()

            if user_input == "":
                max_tips = None  # ВСЕ доступные
                print("Будут загружены ВСЕ доступные прогнозы (пока не закончатся)")
                break
            else:
                max_tips = int(user_input)
                if max_tips > 0:
                    print(f"Будут загружены {max_tips} прогнозов")
                    break
                else:
                    print("Введите положительное число или Enter для ВСЕХ прогнозов")
        except ValueError:
            print("Пожалуйста, введите число или нажмите Enter для ВСЕХ прогнозов")

    # Создаем сессию
    session = create_session()
    if not session:
        print("Не удалось создать сессию. Проверьте логин/пароль.")
        return

    print("\n3. Загружаю список прогнозов...")

    # Загружаем прогнозы
    all_tips = []
    skip = 0
    page = 1

    while True:
        print(f"  Страница {page}: загружаю прогнозы {skip + 1}-{skip + 10}...")

        response = session.get(API_LIST_URL, params={'skip': skip})

        if response.status_code != 200:
            print(f"  Ошибка: {response.status_code}")
            break

        batch = response.json()
        if not batch:
            print("  Больше нет прогнозов.")
            break

        # Если указано конкретное количество
        if max_tips is not None:
            needed = max_tips - len(all_tips)
            if needed <= 0:
                break

            if len(batch) <= needed:
                all_tips.extend(batch)
            else:
                all_tips.extend(batch[:needed])
                break
        else:
            # Загружаем ВСЕ
            all_tips.extend(batch)

        skip += 10
        page += 1

        # Если пришло меньше 10, значит это последняя страница
        if len(batch) < 10:
            break

        time.sleep(0.1)

    print(f"\n✓ Загружено {len(all_tips)} прогнозов")

    # Парсим детали
    print("\n4. Парсим детали прогнозов...")
    data = []
    failed = 0

    for i, tip in enumerate(all_tips, 1):
        reference = tip.get('reference')
        print(f"  [{i}/{len(all_tips)}] Обрабатываю {reference[:30]}...")

        # Получаем fixtureReference
        fixture_reference = get_fixture_reference_from_tip(session, reference)

        if not fixture_reference:
            print(f"    ⚠ Не найден fixtureReference")
            failed += 1
            continue

        details = parse_tip_details(session, reference, fixture_reference)
        if details:
            data.append(details)
            # Показываем разницу между оригинальным и нашим профитом
            odds = details.get('odds', 0)
            result = details.get('result', '')
            our_profit = details.get('profit', 0)
            original_profit = details.get('original_profit', 0)

            print(f"    ✓ {details.get('match')} - {details.get('bet')} @ {odds}")
            print(f"       Result: {result}, Odds: {odds}, Our profit: {our_profit}, Original: {original_profit}")
        else:
            print(f"    ✗ Не удалось получить данные")
            failed += 1

        # Задержка
        time.sleep(0.1)

    # Сохраняем в Excel
    if data:
        print(f"\n5. Сохраняю {len(data)} результатов в Excel...")
        print(f"   Успешно: {len(data)}, Не удалось: {failed}")

        df = pd.DataFrame(data)

        # Упорядочиваем колонки
        columns_order = [
            'event_date', 'event_time', 'home_team', 'away_team', 'match',
            'market', 'bet', 'odds', 'result', 'profit', 'original_profit',
            'sport', 'league', 'raw_result_code', 'reference'
        ]

        # Фильтруем только существующие колонки
        existing_columns = [col for col in columns_order if col in df.columns]
        df = df[existing_columns]

        # Сохраняем
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'tipstrr_results_{timestamp}.xlsx'

        df.to_excel(filename, index=False)
        print(f"✓ Файл сохранен: {os.path.abspath(filename)}")

        # Статистика
        print(f"\nСтатистика результатов:")
        result_counts = df['result'].value_counts()
        for result, count in result_counts.items():
            print(f"  {result}: {count} ({count / len(data) * 100:.1f}%)")

        # Общий профит
        total_profit = df['profit'].sum()
        print(f"  Общий профит (наш расчет): {total_profit:.2f}")
        if 'original_profit' in df.columns:
            total_original_profit = df['original_profit'].sum()
            print(f"  Общий профит (оригинальный): {total_original_profit:.2f}")
            print(f"  Разница: {total_profit - total_original_profit:.2f}")

        print(f"\nПервые 5 строк:")
        print(df.head().to_string(index=False))

        # Дополнительно сохраняем в CSV для удобства
        csv_filename = f'tipstrr_results_{timestamp}.csv'
        df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        print(f"✓ Также сохранено в CSV: {csv_filename}")

        # Сохраняем JSON с сырыми данными
        json_filename = f'tipstrr_data_{timestamp}.json'
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✓ Сырые данные сохранены в JSON: {json_filename}")

    else:
        print("\n✗ Нет данных для сохранения.")


if __name__ == "__main__":
    main()
