import requests
import pandas as pd
from datetime import datetime
import time
import os
import json
from getpass import getpass

# КОНФИГУРАЦИЯ
BASE_URL = "https://tipstrr.com"
LOGIN_URL = "https://www.tipstrr.com/login"
API_FIXTURE_URL = f"{BASE_URL}/api/fixture"
REQUEST_TIMEOUT = 20
DEFAULT_TIPSTER_SLUG = os.getenv("TIPSTRR_TIPSTER", "freguli").strip()
USERNAME = os.getenv("TIPSTRR_USERNAME", "")
PASSWORD = os.getenv("TIPSTRR_PASSWORD", "")


def build_tipster_endpoints(tipster_slug):
    """Собирает endpoint-ы для конкретного каппера (slug)."""
    return {
        "api_list_url": f"{BASE_URL}/api/portfolio/{tipster_slug}/tips/completed",
        "api_tip_url": f"{BASE_URL}/api/portfolio/{tipster_slug}/tips/cached",
        "referer": f"https://www.tipstrr.com/tipster/{tipster_slug}/results",
    }


def get_credentials():
    """Получает логин/пароль из переменных окружения или через консоль."""
    username = USERNAME or input("Введите логин Tipstrr (email): ").strip()
    password = PASSWORD or getpass("Введите пароль Tipstrr: ")

    if not username or not password:
        return None, None

    return username, password


def get_tipster_slug():
    """Получает slug каппера для портфолио API."""
    user_slug = input(
        f"Введите slug каппера (Enter = {DEFAULT_TIPSTER_SLUG}): "
    ).strip()
    tipster_slug = user_slug or DEFAULT_TIPSTER_SLUG

    if not tipster_slug:
        return None

    return tipster_slug


def create_session(username, password, referer_url):
    """Создает сессию с авторизацией на сайте"""
    session = requests.Session()

    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': referer_url,
    })

    print("1. Получаем начальные куки...")
    session.get("https://www.tipstrr.com", timeout=REQUEST_TIMEOUT)

    print("2. Логинимся...")
    login_data = {"username": username, "password": password}

    login_headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'https://www.tipstrr.com',
        'Referer': 'https://www.tipstrr.com/login',
    }

    response = session.post(LOGIN_URL, data=login_data, headers=login_headers, timeout=REQUEST_TIMEOUT)

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
    """
    try:
        odds_float = float(odds) if odds else 0
    except (ValueError, TypeError):
        odds_float = 0

    if result_code == 1:
        return odds_float - 1 if odds_float > 0 else 0
    if result_code == 5:
        return 0.0
    return -1.0


def get_result_text(result_code):
    """Преобразует код результата в текст."""
    if result_code == 1:
        return "Win"
    if result_code in (2, 3, 4):
        return "Lose"
    if result_code == 5:
        return "Unknown(5)"
    return f"Unknown ({result_code})"


def parse_tip_details(session, tip_data, reference, fixture_reference):
    """Парсит детали прогноза и матча"""
    try:
        if not isinstance(tip_data, dict):
            print(f"  Некорректный формат tip_data для {reference}")
            return None

        fixture_data = None
        if fixture_reference:
            fixture_url = f"{API_FIXTURE_URL}/{fixture_reference}"
            response_fixture = session.get(fixture_url, timeout=REQUEST_TIMEOUT)

            if response_fixture.status_code == 200:
                fixture_json = response_fixture.json()
                if isinstance(fixture_json, dict):
                    fixture_data = fixture_json

        return extract_tip_data(tip_data, fixture_data, reference)

    except Exception as e:
        print(f"  Ошибка при парсинге {reference}: {e}")
        return None


def extract_tip_data(tip_data, fixture_data, reference):
    """Извлекает данные из JSON ответов"""
    if not isinstance(tip_data, dict):
        return None

    title = tip_data.get('title', '')
    tip_date = tip_data.get('tipDate', '')
    result = tip_data.get('result', '')
    original_profit = tip_data.get('profit', '')

    event_date = ''
    event_time = ''
    if tip_date:
        try:
            dt = datetime.fromisoformat(tip_date.replace('Z', '+00:00'))
            event_date = dt.strftime('%Y-%m-%d')
            event_time = dt.strftime('%H:%M')
        except ValueError:
            event_date = tip_date[:10] if len(tip_date) >= 10 else tip_date

    odds = None
    market_text = ''
    bet_text = ''

    tip_bet = tip_data.get('tipBet')
    if isinstance(tip_bet, list) and tip_bet:
        first_tip_bet = tip_bet[0] or {}
        if isinstance(first_tip_bet, dict):
            odds = first_tip_bet.get('odds', '')

    tip_bet_item = tip_data.get('tipBetItem')
    if isinstance(tip_bet_item, list) and tip_bet_item:
        first_tip_bet_item = tip_bet_item[0] or {}
        if isinstance(first_tip_bet_item, dict):
            market_text = first_tip_bet_item.get('marketText', '')
            bet_text = first_tip_bet_item.get('betText', '')

    home_team = ''
    away_team = ''
    sport = ''
    league = ''

    if isinstance(fixture_data, dict):
        home_team = (fixture_data.get('homeTeam') or {}).get('name', '')
        away_team = (fixture_data.get('awayTeam') or {}).get('name', '')
        sport = (fixture_data.get('sport') or {}).get('name', '')
        league = (fixture_data.get('competition') or {}).get('name', '')

    if not home_team and ' v ' in title:
        parts = title.split(' v ')
        if len(parts) == 2:
            home_team = parts[0].strip()
            away_team = parts[1].strip()

    result_text = get_result_text(result)
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
        'profit': correct_profit,
        'original_profit': original_profit,
        'raw_result_code': result,
        'reference': reference
    }


def get_tip_data(session, api_tip_url, reference):
    """Получает детали прогноза по reference."""
    tip_url = f"{api_tip_url}/{reference}"
    response = session.get(tip_url, timeout=REQUEST_TIMEOUT)

    if response.status_code == 200:
        payload = response.json()
        if isinstance(payload, dict):
            return payload
        print(f"  Пустой/неожиданный ответ API по прогнозу {reference}")
        return None

    print(f"  Ошибка при запросе прогноза {reference}: {response.status_code}")
    return None


def get_fixture_reference_from_tip(tip_data):
    """Получает fixtureReference из данных прогноза"""
    if not isinstance(tip_data, dict):
        return None

    tip_bet_item = tip_data.get('tipBetItem')
    if isinstance(tip_bet_item, list) and tip_bet_item:
        first_tip_bet_item = tip_bet_item[0] or {}
        if isinstance(first_tip_bet_item, dict):
            return first_tip_bet_item.get('fixtureReference')

    return None


def main():
    print("=== Парсер Tipstrr.com ===")
    print("=" * 30)

    tipster_slug = get_tipster_slug()
    if not tipster_slug:
        print("Slug каппера не задан.")
        return

    endpoints = build_tipster_endpoints(tipster_slug)
    print(f"Каппер: {tipster_slug}")

    while True:
        try:
            user_input = input(
                "\nСколько прогнозов парсить? (Enter = ВСЕ доступные, число = конкретное количество): "
            ).strip()

            if user_input == "":
                max_tips = None
                print("Будут загружены ВСЕ доступные прогнозы (пока не закончатся)")
                break

            max_tips = int(user_input)
            if max_tips > 0:
                print(f"Будут загружены {max_tips} прогнозов")
                break

            print("Введите положительное число или Enter для ВСЕХ прогнозов")
        except ValueError:
            print("Пожалуйста, введите число или нажмите Enter для ВСЕХ прогнозов")

    username, password = get_credentials()
    if not username or not password:
        print("Логин/пароль не заданы.")
        return

    session = create_session(username, password, endpoints["referer"])
    if not session:
        print("Не удалось создать сессию. Проверьте логин/пароль.")
        return

    print("\n3. Загружаю список прогнозов...")

    all_tips = []
    skip = 0
    page = 1

    while True:
        print(f"  Страница {page}: загружаю прогнозы {skip + 1}-{skip + 10}...")

        response = session.get(
            endpoints["api_list_url"],
            params={'skip': skip},
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code != 200:
            print(f"  Ошибка: {response.status_code}")
            break

        batch = response.json()
        if not isinstance(batch, list) or not batch:
            print("  Больше нет прогнозов.")
            break

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
            all_tips.extend(batch)

        skip += 10
        page += 1

        if len(batch) < 10:
            break

        time.sleep(0.1)

    print(f"\n✓ Загружено {len(all_tips)} прогнозов")

    print("\n4. Парсим детали прогнозов...")
    data = []
    failed = 0

    for i, tip in enumerate(all_tips, 1):
        reference = (tip or {}).get('reference') if isinstance(tip, dict) else None
        if not reference:
            print(f"  [{i}/{len(all_tips)}] ⚠ Пропуск: пустой reference")
            failed += 1
            continue

        print(f"  [{i}/{len(all_tips)}] Обрабатываю {reference[:30]}...")

        tip_data = get_tip_data(session, endpoints["api_tip_url"], reference)
        if not tip_data:
            failed += 1
            continue

        fixture_reference = get_fixture_reference_from_tip(tip_data)
        details = parse_tip_details(session, tip_data, reference, fixture_reference)

        if details:
            data.append(details)
            odds = details.get('odds', 0)
            result = details.get('result', '')
            our_profit = details.get('profit', 0)
            original_profit = details.get('original_profit', 0)

            print(f"    ✓ {details.get('match')} - {details.get('bet')} @ {odds}")
            print(f"       Result: {result}, Odds: {odds}, Our profit: {our_profit}, Original: {original_profit}")
        else:
            print("    ✗ Не удалось получить данные")
            failed += 1

        time.sleep(0.1)

    if data:
        print(f"\n5. Сохраняю {len(data)} результатов в Excel...")
        print(f"   Успешно: {len(data)}, Не удалось: {failed}")

        df = pd.DataFrame(data)
        columns_order = [
            'event_date', 'event_time', 'home_team', 'away_team', 'match',
            'market', 'bet', 'odds', 'result', 'profit', 'original_profit',
            'sport', 'league', 'raw_result_code', 'reference'
        ]

        existing_columns = [col for col in columns_order if col in df.columns]
        df = df[existing_columns]

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'tipstrr_results_{timestamp}.xlsx'

        df.to_excel(filename, index=False)
        print(f"✓ Файл сохранен: {os.path.abspath(filename)}")

        print("\nСтатистика результатов:")
        result_counts = df['result'].value_counts()
        for result, count in result_counts.items():
            print(f"  {result}: {count} ({count / len(data) * 100:.1f}%)")

        total_profit = df['profit'].sum()
        print(f"  Общий профит (наш расчет): {total_profit:.2f}")
        if 'original_profit' in df.columns:
            total_original_profit = df['original_profit'].sum()
            print(f"  Общий профит (оригинальный): {total_original_profit:.2f}")
            print(f"  Разница: {total_profit - total_original_profit:.2f}")

        print("\nПервые 5 строк:")
        print(df.head().to_string(index=False))

        csv_filename = f'tipstrr_results_{timestamp}.csv'
        df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        print(f"✓ Также сохранено в CSV: {csv_filename}")

        json_filename = f'tipstrr_data_{timestamp}.json'
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✓ Сырые данные сохранены в JSON: {json_filename}")

    else:
        print("\n✗ Нет данных для сохранения.")


if __name__ == "__main__":
    main()
