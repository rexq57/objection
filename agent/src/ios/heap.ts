import { colors as c } from "../lib/color";
import { bytesToUTF8 } from "./lib/helpers";
import { IHeapObject } from "./lib/interfaces";

export namespace heap {
  const enumerateInstances = (clazz: string): ObjC.Object[] => {
    if (!ObjC.classes.hasOwnProperty(clazz)) {
      c.log(`Unknown Objective-C class: ${c.redBright(clazz)}`);
      return [];
    }

    const specifier: ObjC.DetailedChooseSpecifier = {
      class: ObjC.classes[clazz],
      subclasses: true, // don't skip subclasses
    };

    return ObjC.chooseSync(specifier);
  };

  export const getInstances = (clazz: string): IHeapObject[] => {
    c.log(
      `${c.blackBright(`Enumerating live instances of`)} ${c.greenBright(
        clazz
      )}...`
    );

    return enumerateInstances(clazz).map((instance): IHeapObject => {
      try {
        return {
          className: instance.$className,
          handle: instance.handle.toString(),
          ivars: instance.$ivars,
          kind: instance.$kind,
          methods: instance.$ownMethods,
          superClass: instance.$superClass.$className,
        };
      } catch (err) {
        c.log(`Warning: ${c.yellowBright(err)}`);
      }
    });
  };

  const resolvePointer = (pointer: string): ObjC.Object => {
    const o = new ObjC.Object(new NativePointer(pointer));
    c.log(
      `${c.blackBright(`Pointer ` + pointer + ` is to class `)}${c.greenBright(
        o.$className
      )}`
    );

    return o;
  };

  export const getIvars = (
    pointer: string,
    toUTF8: boolean
  ): [string, { [name: string]: any }] => {
    const { $className, $ivars } = resolvePointer(pointer);

    const formatValue = (value: any): any => {
      // 判断是否是 ObjC 对象
      if (value instanceof ObjC.Object) {
        return {
          className: value.$className,
          pointer: value.handle,
          value: new ObjC.Object(new NativePointer(value.handle)).toString(),
        };
      }

      // 判断是否是 NativePointer
      if (value instanceof NativePointer) {
        return { type: "NativePointer", address: value.toString() };
      }

      // 判断是否是基础类型
      if (
        typeof value === "string" ||
        typeof value === "number" ||
        typeof value === "boolean"
      ) {
        return value;
      }

      // 默认返回类型和值
      return value;
    };

    // 转换 ivars
    const convertedIvars: { [name: string]: any } = {};
    c.log(c.blackBright(`Converting ivars...`));

    for (const k in $ivars) {
      if ($ivars.hasOwnProperty(k)) {
        const rawValue = $ivars[k];
        convertedIvars[k] = formatValue(
          toUTF8 ? bytesToUTF8(rawValue) : rawValue
        );
      }
    }

    return [$className, convertedIvars];
  };

  export const getMethods = (pointer: string): [string, any[string]] => {
    const { $className, $ownMethods } = resolvePointer(pointer);
    return [$className, $ownMethods];
  };

  export const callInstanceMethod = (
    pointer: string,
    method: string,
    returnString: boolean
  ): void => {
    const i = resolvePointer(pointer);
    c.log(
      `${c.blackBright(`Executing:`)} ${c.greenBright(
        `[${i.$className} ${method}]`
      )}`
    );

    const result = i[method]();

    if (returnString) {
      return result.toString();
    }
    return i[method]();
  };

  export const evaluate = (pointer: string, js: string): void => {
    const ptr = resolvePointer(pointer);
    // tslint:disable-next-line:no-eval
    eval(js);
  };
}
