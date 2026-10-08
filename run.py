"""
run.py — запуск живого существа.

  python run.py          — подключиться к настоящему боту (bot.js, localhost:3000)
  python run.py --mock   — запустить на искусственном теле (для проверки мозга)
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.brain import Brain


def build_adapter(use_mock):
    if use_mock:
        from adapters.mock import MockAdapter
        print("🧪 Искусственное тело (mock)")
        return MockAdapter()
    from adapters.minecraft import MinecraftAdapter
    return MinecraftAdapter()


def main():
    use_mock = '--mock' in sys.argv
    print("=" * 50)
    print("ЖИВОЕ СУЩЕСТВО v20: ОЩУЩЕНИЕ → ВНИМАНИЕ → ДЕЙСТВИЕ")
    print("=" * 50)

    adapter = build_adapter(use_mock)
    state = adapter.get_state()
    if state is None:
        print("⚠️  Бот не отвечает на localhost:3000")
        print("   Запусти 'node bot.js' в другом окне")
        print("   Или проверь мозг без Minecraft: python run.py --mock")
        return

    brain = Brain(adapter)
    print("💚 Создатель:", brain.self_model.creator or brain.memory.creator_name)

    save_counter = 0
    max_steps = None
    for a in sys.argv:
        if a.startswith('--steps='):
            max_steps = int(a.split('=')[1])

    while True:
        state = adapter.get_state()
        if state is None:
            time.sleep(1)
            continue

        try:
            brain.think(state)
        except KeyboardInterrupt:
            break
        except Exception as e:
            import traceback
            print(f"Ошибка в цикле: {e}")
            traceback.print_exc()

        save_counter += 1
        if save_counter >= 40:
            brain.memory.save()
            brain.skills.save()
            brain.neuromod.save()
            brain.predictor.save_periodic()
            brain.episodic.save()
            brain.self_model.save()
            save_counter = 0

        if brain.step % 20 == 0:
            d = brain.drives.to_dict()
            n = brain.neuromod
            t = brain.drives.tension()
            p = state.get('player')
            enemy = state.get('nearest_hostile')
            night = "🌙" if state.get('is_night') else "☀️"
            pi = ""
            if p:
                dd = p['distance']
                bond = "💚" if dd < 5 else ("🏃" if dd < 25 else "😢")
                pi = f" | {p['name']}:{dd:.0f}м{bond}"
            ei = f" | ⚠️ {enemy['name']} {enemy['distance']:.0f}м" if enemy else ""
            print(
                f"{night} Шаг {brain.step}: "
                f"напряж {t:.2f} (голод {d['hunger']} страх {d['fear']} "
                f"боль {d['pain']} скуч {d['boredom']} один {d['loneliness']}) | "
                f"доф {n.dopamine:.2f} сер {n.serotonin:.2f} корт {n.cortisol:.2f} | "
                f"{n.emotion}{pi}{ei}"
            )
            print(f"   👁  {brain.workspace.summary()}")
            print(f"   🧩 {brain.wm.summary()}")

        if max_steps and brain.step >= max_steps:
            print(f"✅ Достигнут лимит шагов ({max_steps})")
            break

        time.sleep(0.5)


if __name__ == "__main__":
    main()
