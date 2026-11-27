# android_device_xiaomi_mondrian-kernel

Готовое ядро PixelExperience-Reborn (Android 17) для **mondrian**
(POCO F5 Pro / Redmi K60, SM8475). Путь в дереве: `device/xiaomi/mondrian-kernel`.

Здесь нет исходного кода — только результат выпускающей сборки нашего CI,
как в AOSP хранятся `device/google/*-kernel` для Pixel. Исходники — три
репозитория организации, они единственный источник правды:

| Источник | Репозиторий |
|---|---|
| ядро | [android_kernel_xiaomi_sm8450](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450) |
| внешние модули Qualcomm/Xiaomi | [android_kernel_xiaomi_sm8450-modules](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules) |
| device tree | [android_kernel_xiaomi_sm8450-devicetrees](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-devicetrees) |

Ядро распространяется по GPL-2.0; точные исходники каждого выпуска указаны в
`provenance.json`.

## Состав выпуска

| Файл | Куда попадает | Как в стоке OS3.0.8.0 |
|---|---|---|
| `Image` | `boot` | ядро в `boot` (header v4) |
| `dtbs/cape.dtb`, `dtbs/capep.dtb`, `dtbs/cape-v2.dtb` | DTB в `vendor_boot` | базовые DTB Cape (msm-id 0x212/0x213/0x21c) |
| `dtbo.img` | раздел `dtbo` | один оверлей mondrian: msm-id 530/531/540, board-id `0x10008 0x0` |
| `vendor_ramdisk/*.ko`, `modules.load`, `modules.load.recovery` | ramdisk `vendor_boot` | модули первой стадии и recovery |
| `vendor_dlkm/*.ko`, `modules.load` | раздел `vendor_dlkm` | остальные модули |

Дерево устройства дополнительно кладёт в ramdisk `vendor_boot` шесть модулей
аудио/ADSP из `vendor_dlkm` (`q6_pdr` … `adsp_loader`) и грузит их в recovery
после `modules.load.recovery` (`MONDRIAN_RECOVERY_DLKM` в `BoardConfig.mk`).
| `provenance.json` | — | паспорт происхождения |

## Паспорт происхождения (`provenance.json`)

- точные коммиты ядра, модулей и DT (все — репозитории PixelExperience-Reborn);
- компилятор (`clang`) и коммит его prebuilt;
- репозиторий, workflow и номер запуска CI, который собрал выпуск;
- `kernel_release` (vermagic модулей);
- sha256 каждого файла.

`tools/verify_prebuilt.py` проверяет, что каждый файл совпадает с паспортом,
списки загрузки называют только поставляемые модули, а у всех модулей
vermagic нашего ядра. CI запускает проверку на каждый push.

## Как обновлять

Новый выпуск собирает выпускающий режим CI в
`android_kernel_xiaomi_sm8450-modules` теми же шагами, что и проверочная
сборка; его результат коммитится сюда целиком, одним коммитом, вместе с
`provenance.json`. Файлы вручную не правятся.
