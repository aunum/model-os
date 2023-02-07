from modelos.env.image.build import build_containerfile, build_img, push_img


def test_build_image():
    try:
        dockerfile = build_containerfile()
        print("containerfile:", str(dockerfile))
    except Exception as e:
        assert False, f"build_containerfile raised exception {e}"

    try:
        image_id = build_img(dockerfile)
        print("image id:", image_id)
    except Exception as e:
        assert False, f"build_image raised exception {e}"

    try:
        push_img(image_id)
    except Exception as e:
        assert False, f"push_image raised exception {e}"
